from __future__ import annotations

import os
import hmac
import json
import uuid
import hashlib
from datetime import datetime
from functools import wraps
from typing import Optional

from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    send_from_directory,
    make_response,
)
from werkzeug.utils import secure_filename

# ------ DB (sqlite, sem SQLAlchemy) ------
from db import init_db
from db.models import (
    get_or_create_session,
    consume_session_credit_atomic,
    consume_user_credit_atomic,
    record_analysis,
    get_user_by_email,
    create_user,
)

# ------ Utils ------
from utils.security import hash_ip, hash_ua, hash_password, verify_password
from utils.rate_limit import SimpleRateLimiter

# ------ Serviços ------
from services.openai_client import OpenAIClient
from payments import get_payment_provider  # garante que payments/__init__.py expose get_payment_provider

# ==========================================================
# Config
# ==========================================================
app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-influe")

# Políticas / Operação
FREE_CREDITS = int(os.environ.get("FREE_CREDITS", "3"))
MAX_UPLOAD_MB = int(os.environ.get("MAX_UPLOAD_MB", "4"))
TEMP_RETENTION_DAYS = int(os.environ.get("TEMP_RETENTION_DAYS", "7"))
RATE_LIMIT_PER_MINUTE = int(os.environ.get("RATE_LIMIT_PER_MINUTE", "6"))
RATE_LIMIT_MIN_INTERVAL_MS = int(os.environ.get("RATE_LIMIT_MIN_INTERVAL_MS", "1000"))

# Uploads
BASE_DIR = os.path.dirname(__file__)
STORAGE_DIR = os.path.join(BASE_DIR, "storage", "temp")
os.makedirs(STORAGE_DIR, exist_ok=True)

# Inicializa DB
try:
    init_db()
    print("[BOOT] DB inicializado.")
except Exception as e:
    print(f"[BOOT][WARN] init_db falhou: {e}")

# IA client (stub por padrão)
ai_client = OpenAIClient()

# Rate limiter simples
rate_limiter = SimpleRateLimiter(
    window_s=60,
    max_requests=RATE_LIMIT_PER_MINUTE,
    min_interval_s=RATE_LIMIT_MIN_INTERVAL_MS / 1000.0,
)

# ==========================================================
# Helpers de sessão e auth
# ==========================================================
def _ip_hash() -> str:
    ip = request.headers.get("X-Forwarded-For", request.remote_addr) or ""
    return hash_ip(ip)

def _ua_hash() -> str:
    ua = (request.headers.get("User-Agent", "") or "") + "|" + (request.headers.get("Accept", "") or "")
    return hash_ua(ua)

def _get_session_id() -> Optional[str]:
    return request.cookies.get("influe_session")

def _ensure_session_cookie(resp, session_id: str):
    resp.set_cookie(
        "influe_session",
        session_id,
        max_age=60 * 60 * 24 * 7,
        httponly=True,
        samesite="Lax",
        secure=False if app.debug else True,
    )
    return resp

# --- Token HMAC simples (MVP) ---
def _make_token(user_id: int) -> str:
    secret = app.config["SECRET_KEY"].encode()
    msg = str(user_id).encode()
    sig = hmac.new(secret, msg, hashlib.sha256).hexdigest()
    return f"{user_id}.{sig}"

def _parse_token(token: str) -> Optional[int]:
    try:
        user_str, sig = token.split(".", 1)
        secret = app.config["SECRET_KEY"].encode()
        exp = hmac.new(secret, user_str.encode(), hashlib.sha256).hexdigest()
        if hmac.compare_digest(exp, sig):
            return int(user_str)
    except Exception:
        return None
    return None

def require_auth_maybe(fn):
    """Decorator que injeta user_id (ou None) no handler."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        user_id = None
        if auth.startswith("Bearer "):
            maybe = auth.replace("Bearer ", "", 1).strip()
            user_id = _parse_token(maybe)
        return fn(user_id, *args, **kwargs)
    return wrapper

def rate_limit(fn):
    """Decorator de rate-limit por IP."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        key = request.headers.get("X-Forwarded-For", request.remote_addr) or "unknown"
        if not rate_limiter.allow(key):
            return jsonify({"ok": False, "error": "Muitas requisições. Tente novamente em instantes."}), 429
        return fn(*args, **kwargs)
    return wrapper

# ==========================================================
# Seed do ADMIN (admin@gmail.com / @123456)
# ==========================================================
def _seed_admin_if_missing():
    """
    Cria usuário admin com muitos créditos se ainda não existir.
    Email: admin@gmail.com
    Senha: @123456
    """
    from db.models import db_cursor  # import local

    admin = get_user_by_email("admin@gmail.com")
    if admin:
        return

    salt, hashed = hash_password("@123456")
    user_id = create_user(
        email="admin@gmail.com",
        password_hash=f"{salt}${hashed}",
        credits=0  # ajustaremos abaixo
    )
    # Dá "acesso completo" prático: um volume alto de créditos
    with db_cursor() as cur:
        cur.execute("UPDATE users SET credits_remaining = ? WHERE id = ?", (999999, user_id))
    print("[BOOT] Usuário admin criado (admin@gmail.com).")

try:
    _seed_admin_if_missing()
except Exception as e:
    print(f"[BOOT][WARN] Seed admin falhou: {e}")

# ==========================================================
# Helpers de gating (login só após consumir 3 créditos)
# ==========================================================
def _session_ensure_and_get_id() -> str:
    session_id = _get_session_id()
    if not session_id:
        session_id = str(uuid.uuid4())
        get_or_create_session(session_id, _ip_hash(), _ua_hash(), FREE_CREDITS)
    return session_id

def _has_any_credit(user_id: Optional[int], session_id: Optional[str]) -> bool:
    from db.models import db_cursor
    with db_cursor() as cur:
        # Créditos do usuário logado
        if user_id:
            cur.execute("SELECT credits_remaining FROM users WHERE id = ?", (user_id,))
            row = cur.fetchone()
            if row and (row["credits_remaining"] or 0) > 0:
                return True
        # Créditos da sessão
        if session_id:
            cur.execute("SELECT credits_temp_remaining FROM sessions WHERE session_id = ?", (session_id,))
            row = cur.fetchone()
            if row and (row["credits_temp_remaining"] or 0) > 0:
                return True
    return False

# ==========================================================
# Rotas Web (home/landing)
# ==========================================================
@app.get("/")
def home():
    # Nunca abre modal de login automaticamente.
    # Garante cookie/sessão com 3 créditos (se nova).
    credits_left_placeholder = 3  # só visual; o real vem do /credits_status via JS
    resp = make_response(render_template("index.html", credits_left=credits_left_placeholder))
    if not _get_session_id():
        sid = str(uuid.uuid4())
        get_or_create_session(sid, _ip_hash(), _ua_hash(), FREE_CREDITS)
        _ensure_session_cookie(resp, sid)
    return resp

@app.get("/privacy")
def privacy():
    return jsonify({
        "ok": True,
        "policy": f"Dados minimizados; imagens temporárias por até {TEMP_RETENTION_DAYS} dias; créditos por sessão/usuário."
    })

@app.get("/health")
def health():
    return jsonify({"status": "ok", "time": datetime.utcnow().isoformat()})

# ==========================================================
# Gate de login (frontend decide abrir modal apenas quando preciso)
# ==========================================================
@app.get("/gate/login")
@require_auth_maybe
def gate_login(user_id: Optional[int]):
    """
    Regras:
      - Se usuário logado tiver créditos > 0 => não obrigar login.
      - Se não logado e sessão tiver créditos > 0 => não obrigar login.
      - Caso contrário => obrigar login (para comprar créditos / histórico).
    """
    session_id = _get_session_id()
    if _has_any_credit(user_id, session_id):
        return jsonify({"ok": True, "require_login": False})
    return jsonify({"ok": True, "require_login": True, "reason": "Sem créditos; faça login para comprar."})

# ==========================================================
# Status de créditos
# ==========================================================
@app.get("/credits_status")
@require_auth_maybe
def credits_status(user_id: Optional[int]):
    from db.models import db_cursor  # import local
    session_id = _get_session_id()
    user_credits = None
    session_credits = None

    with db_cursor() as cur:
        if session_id:
            cur.execute("SELECT credits_temp_remaining FROM sessions WHERE session_id = ?", (session_id,))
            r = cur.fetchone()
            if r:
                session_credits = r["credits_temp_remaining"]

        if user_id:
            cur.execute("SELECT credits_remaining FROM users WHERE id = ?", (user_id,))
            u = cur.fetchone()
            if u:
                user_credits = u["credits_remaining"]

    return jsonify({"ok": True, "data": {"session": session_credits, "user": user_credits}})

# ==========================================================
# Auth simples (email + senha)
# ==========================================================
@app.post("/auth/register")
def auth_register():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    if not email or not password:
        return jsonify({"ok": False, "error": "Email e senha são obrigatórios."}), 400

    if get_user_by_email(email):
        return jsonify({"ok": False, "error": "Email já cadastrado."}), 409

    salt, hashed = hash_password(password)
    user_id = create_user(email=email, password_hash=f"{salt}${hashed}", credits=0)
    token = _make_token(user_id)
    return jsonify({"ok": True, "token": token, "user_id": user_id})

@app.post("/auth/login")
def auth_login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    if not email or not password:
        return jsonify({"ok": False, "error": "Email e senha são obrigatórios."}), 400

    user = get_user_by_email(email)
    if not user:
        return jsonify({"ok": False, "error": "Credenciais inválidas."}), 401

    # password_hash armazenado como "salt$hash"
    from db.models import db_cursor
    with db_cursor() as cur:
        cur.execute("SELECT password_hash FROM users WHERE id = ?", (user.id,))
        row = cur.fetchone()
        if not row:
            return jsonify({"ok": False, "error": "Credenciais inválidas."}), 401
        try:
            salt, stored_hex = row["password_hash"].split("$", 1)
        except Exception:
            return jsonify({"ok": False, "error": "Credenciais inválidas."}), 401

    if not verify_password(password, salt, stored_hex):
        return jsonify({"ok": False, "error": "Credenciais inválidas."}), 401

    token = _make_token(user.id)
    return jsonify({"ok": True, "token": token, "user_id": user.id})

@app.get("/user/profile")
@require_auth_maybe
def user_profile(user_id: Optional[int]):
    if not user_id:
        return jsonify({"ok": True, "data": {"logged_in": False, "history": []}})

    from db.models import db_cursor
    with db_cursor() as cur:
        cur.execute(
            "SELECT id, type, score_risk, tags, created_at FROM analyses WHERE user_id = ? ORDER BY created_at DESC LIMIT 50",
            (user_id,),
        )
        rows = cur.fetchall()
        history = []
        for r in rows:
            try:
                tags = json.loads(r["tags"]) if r["tags"] else []
            except Exception:
                tags = []
            history.append({
                "id": r["id"],
                "type": r["type"],
                "score_risk": r["score_risk"],
                "tags": tags,
                "created_at": r["created_at"],
            })

        cur.execute("SELECT credits_remaining FROM users WHERE id = ?", (user_id,))
        uc = cur.fetchone()
        credits_remaining = uc["credits_remaining"] if uc else 0

    return jsonify({"ok": True, "data": {"logged_in": True, "credits_remaining": credits_remaining, "history": history}})

# ==========================================================
# Analyze Photo / Text
# ==========================================================
def _ensure_session() -> str:
    session_id = _get_session_id()
    if not session_id:
        session_id = str(uuid.uuid4())
        get_or_create_session(session_id, _ip_hash(), _ua_hash(), FREE_CREDITS)
    return session_id

@app.post("/analyze_photo")
@rate_limit
@require_auth_maybe
def analyze_photo(user_id: Optional[int]):
    session_id = _ensure_session()

    file = request.files.get("file") or request.files.get("photo")
    if not file or not file.filename:
        return jsonify({"ok": False, "error": "Nenhuma imagem enviada."}), 400

    filename = secure_filename(file.filename.lower())
    if not any(filename.endswith(ext) for ext in [".jpg", ".jpeg", ".png"]):
        return jsonify({"ok": False, "error": "Formato inválido. Use JPG/PNG."}), 400

    file.seek(0, os.SEEK_END)
    size_mb = file.tell() / (1024 * 1024)
    file.seek(0)
    if size_mb > MAX_UPLOAD_MB:
        return jsonify({"ok": False, "error": f"Arquivo excede {MAX_UPLOAD_MB}MB."}), 400

    session_dir = os.path.join(STORAGE_DIR, session_id)
    os.makedirs(session_dir, exist_ok=True)
    save_path = os.path.join(session_dir, filename)
    file.save(save_path)

    ok = False
    if user_id:
        ok = consume_user_credit_atomic(user_id)
    if not ok:
        ok = consume_session_credit_atomic(session_id)
    if not ok:
        return jsonify({"ok": False, "error": "Sem créditos disponíveis. Faça login e/ou compre créditos."}), 402

    result = ai_client.analyze_image(save_path)
    if not result.get("ok"):
        return jsonify({"ok": False, "error": result.get("error", "Falha na análise de IA.")}), 502

    meta = json.dumps({"filename": filename})
    tags = json.dumps(result.get("tags", []))
    score = int(result.get("score_risk", 0))
    record_analysis(user_id=user_id, session_id=session_id, a_type="photo", meta=meta, score_risk=score, tags=tags)

    return jsonify({"ok": True, "analysis": result})

@app.post("/analyze_text")
@rate_limit
@require_auth_maybe
def analyze_text(user_id: Optional[int]):
    session_id = _ensure_session()

    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip()
    if not text:
        return jsonify({"ok": False, "error": "Texto vazio."}), 400

    ok = False
    if user_id:
        ok = consume_user_credit_atomic(user_id)
    if not ok:
        ok = consume_session_credit_atomic(session_id)
    if not ok:
        return jsonify({"ok": False, "error": "Sem créditos disponíveis. Faça login e/ou compre créditos."}), 402

    result = ai_client.analyze_text(text)
    if not result.get("ok"):
        return jsonify({"ok": False, "error": result.get("error", "Falha na análise de IA.")}), 502

    meta = json.dumps({"chars": len(text)})
    tags = json.dumps(result.get("tags", []))
    score = int(result.get("score_risk", 0))
    record_analysis(user_id=user_id, session_id=session_id, a_type="text", meta=meta, score_risk=score, tags=tags)

    return jsonify({"ok": True, "analysis": result})

# ==========================================================
# Pagamentos (Mock)
# ==========================================================
@app.post("/purchase")
@require_auth_maybe
def purchase(user_id: Optional[int]):
    if not user_id:
        return jsonify({"ok": False, "error": "É necessário login para comprar créditos."}), 401

    data = request.get_json(silent=True) or {}
    package = int(data.get("package") or 10)  # 10, 20, 50

    provider = get_payment_provider()
    checkout = provider.start_checkout(user_id=user_id, package=package)
    return jsonify({"ok": checkout.get("ok", False), "checkout": checkout})

# ==========================================================
# Servir arquivos temporários (debug/local)
# ==========================================================
@app.get("/storage/temp/<session_id>/<path:fname>")
def serve_temp(session_id, fname):
    return send_from_directory(os.path.join(STORAGE_DIR, session_id), fname)

# ==========================================================
# Boot local
# ==========================================================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
