from __future__ import annotations

import os
import hmac
import json
import uuid
import hashlib
from datetime import datetime
from functools import wraps
from typing import Optional, Tuple

from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    send_from_directory,
    make_response,
)
from werkzeug.utils import secure_filename

# ------ DB init / schema helpers ------
from db.models import (
    init_db,
    get_or_create_session,
    consume_session_credit_atomic,
    consume_user_credit_atomic,
    record_analysis,
    get_user_by_email,
    create_user,
)
from db.models import db_cursor  # para consultas diretas de purchases
from db.models import add_credits_to_user  # crédito automático pós-pagamento
from db.models import count_recent_users_by_ip  # <— NOVO: checagem de abuso por IP

# ------ Utils ------
from utils.security import hash_ip, hash_ua, hash_password, verify_password
from utils.rate_limit import SimpleRateLimiter

# ------ Serviços ------
from services.openai_client import OpenAIClient
from payments import get_payment_provider  # garante public get_payment_provider

# ==========================================================
# Config
# ==========================================================
app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-influe")

# Políticas / Operação
# Sessão desativada para gratuidade: FREE_CREDITS=0 no Render (conforme combinado)
FREE_CREDITS = int(os.environ.get("FREE_CREDITS", "0"))
MAX_UPLOAD_MB = int(os.environ.get("MAX_UPLOAD_MB", "4"))
TEMP_RETENTION_DAYS = int(os.environ.get("TEMP_RETENTION_DAYS", "7"))
RATE_LIMIT_PER_MINUTE = int(os.environ.get("RATE_LIMIT_PER_MINUTE", "6"))
RATE_LIMIT_MIN_INTERVAL_MS = int(os.environ.get("RATE_LIMIT_MIN_INTERVAL_MS", "1000"))

# Pagamentos / Webhook
PAGBANK_WEBHOOK_SECRET = os.environ.get("PAGBANK_WEBHOOK_SECRET", "").encode()  # pode estar vazio em dev
PAGBANK_TOKEN = os.environ.get("PAGBANK_TOKEN", "")

# Uploads
BASE_DIR = os.path.dirname(__file__)
STORAGE_DIR = os.path.join(BASE_DIR, "storage", "temp")
os.makedirs(STORAGE_DIR, exist_ok=True)

# Inicializa DB / cria tabelas
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
# Compat SQLite x Postgres (para placeholders em logs locais)
# ==========================================================
_IS_PG = os.environ.get("DATABASE_URL", "").startswith(("postgresql://", "postgres://"))
def _sql(q: str) -> str:
    return q.replace("?", "%s") if _IS_PG else q

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
    try:
        admin = get_user_by_email("admin@gmail.com")
        if admin:
            return
        salt, hashed = hash_password("@123456")
        # ip_hash não é necessário para admin seed
        user_id = create_user(
            email="admin@gmail.com",
            password_hash=f"{salt}${hashed}",
            credits=0,
            ip_hash=None,  # <— compatível com nova assinatura
        )
        # dá muitos créditos
        with db_cursor() as cur:
            cur.execute(_sql("UPDATE users SET credits_remaining = ? WHERE id = ?"), (999999, user_id))
        print("[BOOT] Usuário admin criado (admin@gmail.com).")
    except Exception as e:
        print(f"[BOOT][WARN] Seed admin falhou: {e}")

_seed_admin_if_missing()

# ==========================================================
# Rota admin para diagnosticar a conexão / criar schema
# ==========================================================
@app.get("/__admin/ensure_schema")
def __admin_ensure_schema():
    token = request.args.get("token")
    if token != os.environ.get("SETUP_TOKEN", ""):
        return jsonify({"ok": False, "error": "Forbidden"}), 403
    try:
        init_db()
        with db_cursor() as cur:
            cur.execute(_sql("SELECT 1"))
            cur.fetchone()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

# ==========================================================
# Helpers de sessão
# ==========================================================
def _session_ensure_and_get_id() -> str:
    session_id = _get_session_id()
    if not session_id:
        session_id = str(uuid.uuid4())
        get_or_create_session(session_id, _ip_hash(), _ua_hash(), FREE_CREDITS)
    return session_id

def _ensure_session_created() -> Tuple[str, bool]:
    sid = _get_session_id()
    if sid:
        return sid, False
    sid = str(uuid.uuid4())
    get_or_create_session(sid, _ip_hash(), _ua_hash(), FREE_CREDITS)
    return sid, True

def _ensure_session_persisted(sid: str) -> None:
    with db_cursor() as cur:
        cur.execute(_sql("SELECT credits_temp_remaining FROM sessions WHERE session_id = ?"), (sid,))
        row = cur.fetchone()
        if not row:
            try:
                cur.execute(
                    _sql("INSERT INTO sessions (session_id, ip_hash, ua_hash, credits_temp_remaining) VALUES (?, ?, ?, ?)"),
                    (sid, _ip_hash(), _ua_hash(), FREE_CREDITS),
                )
            except Exception:
                pass  # corrida

def _has_any_credit(user_id: Optional[int], session_id: Optional[str]) -> bool:
    with db_cursor() as cur:
        if user_id:
            cur.execute(_sql("SELECT credits_remaining FROM users WHERE id = ?"), (user_id,))
            row = cur.fetchone()
            if row and (row["credits_remaining"] or 0) > 0:
                return True
        if session_id:
            cur.execute(_sql("SELECT credits_temp_remaining FROM sessions WHERE session_id = ?"), (session_id,))
            row = cur.fetchone()
            if row and (row["credits_temp_remaining"] or 0) > 0:
                return True
    return False

# ==========================================================
# Web
# ==========================================================
@app.get("/")
def home():
    credits_left_placeholder = 0  # sessão não concede créditos
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

# --- Página de compra ---
@app.get("/buy")
@require_auth_maybe
def buy_page(user_id: Optional[int]):
    return render_template("buy.html")

@app.get("/gate/login")
@require_auth_maybe
def gate_login(user_id: Optional[int]):
    sid, created_now = _ensure_session_created()
    _ensure_session_persisted(sid)
    has_cookie = bool(_get_session_id())

    if _has_any_credit(user_id, sid):
        payload = {"ok": True, "require_login": False, "logged_in": bool(user_id)}
        resp = make_response(jsonify(payload))
        if created_now or not has_cookie:
            _ensure_session_cookie(resp, sid)
        return resp

    if user_id:
        payload = {"ok": True, "require_login": False, "logged_in": True, "need_purchase": True}
        resp = make_response(jsonify(payload))
        if created_now or not has_cookie:
            _ensure_session_cookie(resp, sid)
        return resp

    payload = {"ok": True, "require_login": True, "logged_in": False, "reason": "Sem créditos; faça login para comprar."}
    resp = make_response(jsonify(payload))
    if created_now or not has_cookie:
        _ensure_session_cookie(resp, sid)
    return resp

# ==========================================================
# Status de créditos
# ==========================================================
@app.get("/credits_status")
@require_auth_maybe
def credits_status(user_id: Optional[int]):
    sid, created_now = _ensure_session_created()
    _ensure_session_persisted(sid)

    user_credits = None
    session_credits = None
    with db_cursor() as cur:
        cur.execute(_sql("SELECT credits_temp_remaining FROM sessions WHERE session_id = ?"), (sid,))
        r = cur.fetchone()
        if r:
            raw = r["credits_temp_remaining"]
            if raw is None:
                cur.execute(_sql("UPDATE sessions SET credits_temp_remaining = ? WHERE session_id = ?"),
                            (FREE_CREDITS, sid))
                session_credits = FREE_CREDITS
            else:
                session_credits = raw
        if user_id:
            cur.execute(_sql("SELECT credits_remaining FROM users WHERE id = ?"), (user_id,))
            u = cur.fetchone()
            if u:
                user_credits = u["credits_remaining"]

    payload = {"ok": True, "data": {"session": session_credits, "user": user_credits, "free_credits": FREE_CREDITS}}
    resp = make_response(jsonify(payload))
    if created_now or not _get_session_id():
        _ensure_session_cookie(resp, sid)
    return resp

# ==========================================================
# Auth
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

    # ---------- Mitigação por IP (Etapa 1) ----------
    iph = _ip_hash()
    already = count_recent_users_by_ip(iph, days=30)
    initial_credits = 3 if already == 0 else 0
    # -----------------------------------------------

    salt, hashed = hash_password(password)
    user_id = create_user(
        email=email,
        password_hash=f"{salt}${hashed}",
        credits=initial_credits,
        ip_hash=iph,  # persistimos o ip_hash do cadastro
    )
    token = _make_token(user_id)
    return jsonify({
        "ok": True,
        "token": token,
        "user_id": user_id,
        "granted_credits": initial_credits,
    })

@app.post("/auth/login")
def auth_login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = (data.get("password") or "")
    if not email or not password:
        return jsonify({"ok": False, "error": "Email e senha são obrigatórios."}), 400
    user = get_user_by_email(email)
    if not user:
        return jsonify({"ok": False, "error": "Credenciais inválidas."}), 401
    with db_cursor() as cur:
        cur.execute(_sql("SELECT password_hash FROM users WHERE id = ?"), (user.id,))
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
    with db_cursor() as cur:
        cur.execute(
            _sql("SELECT id, type, score_risk, tags, created_at FROM analyses WHERE user_id = ? ORDER BY created_at DESC LIMIT 50"),
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
        cur.execute(_sql("SELECT credits_remaining FROM users WHERE id = ?"), (user_id,))
        uc = cur.fetchone()
        credits_remaining = uc["credits_remaining"] if uc else 0
    return jsonify({"ok": True, "data": {"logged_in": True, "credits_remaining": credits_remaining, "history": history}})

# ==========================================================
# Analyze
# ==========================================================
def _ensure_session() -> Tuple[str, bool]:
    """
    Garante sessão; retorna (session_id, created_now).
    Importante para endpoints JSON conseguirem setar cookie quando a sessão é criada aqui.
    """
    session_id = _get_session_id()
    if session_id:
        return session_id, False
    session_id = str(uuid.uuid4())
    get_or_create_session(session_id, _ip_hash(), _ua_hash(), FREE_CREDITS)
    return session_id, True

@app.post("/analyze_photo")
@rate_limit
@require_auth_maybe
def analyze_photo(user_id: Optional[int]):
    session_id, created_now = _ensure_session()
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

    resp = make_response(jsonify({"ok": True, "analysis": result}))
    if created_now:
        _ensure_session_cookie(resp, session_id)
    return resp

@app.post("/analyze_text")
@rate_limit
@require_auth_maybe
def analyze_text(user_id: Optional[int]):
    session_id, created_now = _ensure_session()
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
        return jsonify({"ok": False, "error": "Falha na análise de IA."}), 502

    meta = json.dumps({"chars": len(text)})
    tags = json.dumps(result.get("tags", []))
    score = int(result.get("score_risk", 0))
    record_analysis(user_id=user_id, session_id=session_id, a_type="text", meta=meta, score_risk=score, tags=tags)

    resp = make_response(jsonify({"ok": True, "analysis": result}))
    if created_now:
        _ensure_session_cookie(resp, session_id)
    return resp

# ==========================================================
# Pagamentos (mock + webhook PagBank)
# ==========================================================
@app.post("/purchase")
@require_auth_maybe
def purchase(user_id: Optional[int]):
    if not user_id:
        return jsonify({"ok": False, "error": "É necessário login para comprar créditos."}), 401
    data = request.get_json(silent=True) or {}
    package = int(data.get("package") or 10)
    provider = get_payment_provider()
    checkout = provider.start_checkout(user_id=user_id, package=package)
    return jsonify({"ok": checkout.get("ok", False), "checkout": checkout})

# --------- Webhook PagBank ---------
def _read_header_any(*names: str) -> str:
    # Render/WSGI podem normalizar maiúsculas; tentamos várias chaves
    for n in names:
        v = request.headers.get(n)
        if v:
            return v
    return ""

def _hmac_safe_compare(a: bytes, b: bytes) -> bool:
    if len(a) != len(b):
        return False
    return hmac.compare_digest(a, b)

def _verify_pagbank_signature(raw_body: bytes) -> bool:
    """
    Verificação HMAC simples:
    assinatura = hex(HMAC_SHA256(PAGBANK_WEBHOOK_SECRET, raw_body))
    Header aceitos: X-PagBank-Signature, X-Pagbank-Signature, X-Signature
    """
    if not PAGBANK_WEBHOOK_SECRET:
        # Em dev, se não configurar o segredo, aceitamos (mas logamos)
        print("[WEBHOOK][WARN] PAGBANK_WEBHOOK_SECRET não definido; aceitando para dev.")
        return True

    header_sig = _read_header_any("X-PagBank-Signature", "X-Pagbank-Signature", "X-Signature")
    if not header_sig:
        print("[WEBHOOK] Assinatura ausente.")
        return False

    try:
        mac = hmac.new(PAGBANK_WEBHOOK_SECRET, raw_body, hashlib.sha256).hexdigest()
    except Exception as e:
        print(f"[WEBHOOK] Falha ao calcular HMAC: {e}")
        return False
    return _hmac_safe_compare(mac.encode(), header_sig.strip().encode())

def _is_paid_status(s: str) -> bool:
    if not s:
        return False
    s = s.upper()
    # ajuste conforme a docs do PagBank
    return s in ("PAID", "APPROVED", "AUTHORIZED", "CAPTURED", "SUCCEEDED")

@app.post("/webhooks/pagbank")
def webhook_pagbank():
    """
    Webhook idempotente:
    - Verifica assinatura HMAC do corpo bruto.
    - Identifica a compra por reference_id (provider_ref).
    - Se status pagamento "pago" e ainda não marcado, grava 'paid' e credita +package.
    - Responde 200 SEMPRE que processar (ou quando a assinatura for inválida, responde 400).
    """
    raw = request.get_data(cache=False, as_text=False)
    if not _verify_pagbank_signature(raw):
        return jsonify({"ok": False, "error": "signature_invalid"}), 400

    payload = request.get_json(silent=True) or {}
    # Campos tolerantes (variantes comuns):
    provider_ref = (payload.get("reference_id")
                    or payload.get("referenceId")
                    or payload.get("order_id")
                    or payload.get("id")
                    or "")
    status = (payload.get("status") or "").upper()

    if not provider_ref:
        # Sem referência, não conseguimos mapear—confirmamos 200 para não loopar eternamente
        print("[WEBHOOK] reference_id ausente; ignorando.")
        return jsonify({"ok": True, "skipped": True})

    with db_cursor() as cur:
        # Busca a purchase pelo provider_ref
        cur.execute(_sql("SELECT id, user_id, package, status FROM purchases WHERE provider_ref = ?"), (provider_ref,))
        row = cur.fetchone()
        if not row:
            # Pode ser uma compra antiga/local. Respondemos ok para evitar reenvios sem fim.
            print(f"[WEBHOOK] purchase não encontrada para provider_ref={provider_ref}")
            return jsonify({"ok": True, "unknown_purchase": True})

        purchase_id = row["id"]
        user_id = row["user_id"]
        package = int(row["package"] or 10)
        current_status = (row["status"] or "").lower()

        if _is_paid_status(status):
            if current_status == "paid":
                # Idempotência: já creditado
                print(f"[WEBHOOK] purchase {purchase_id} já está paid; ignorando duplicata.")
                return jsonify({"ok": True, "idempotent": True})
            # Marca como pago e credita
            cur.execute(_sql("UPDATE purchases SET status = ? WHERE id = ?"), ("paid", purchase_id))
            try:
                add_credits_to_user(user_id, package)
            except Exception as e:
                # Tentativa de rollback lógico: rebaixa status para pending se crédito falhar
                print(f"[WEBHOOK][ERR] Falha ao creditar usuário {user_id}: {e}")
                try:
                    cur.execute(_sql("UPDATE purchases SET status = ? WHERE id = ?"), ("pending", purchase_id))
                except Exception:
                    pass
                return jsonify({"ok": False, "error": "credit_failed"}), 500

            print(f"[WEBHOOK] Créditos +{package} aplicados ao user_id={user_id} (purchase_id={purchase_id}).")
            return jsonify({"ok": True, "credited": package})
        else:
            # Não pago (pending/canceled/refunded etc.)
            new_status = status.lower() or "pending"
            if new_status != current_status:
                cur.execute(_sql("UPDATE purchases SET status = ? WHERE id = ?"), (new_status, purchase_id))
            return jsonify({"ok": True, "status": new_status})

# ==========================================================
# Servir temp (debug)
# ==========================================================
@app.get("/storage/temp/<session_id>/<path:fname>")
def serve_temp(session_id, fname):
    return send_from_directory(os.path.join(STORAGE_DIR, session_id), fname)

# ==========================================================
# Boot local
# ==========================================================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)

"""
-----------------------------------------------------------
COMO TESTAR O WEBHOOK AGORA (sem PagBank)
-----------------------------------------------------------
1) No Render → Environment:
   - Defina PAGBANK_WEBHOOK_SECRET=teste123

2) Faça um POST simulando o webhook:
   Em um terminal local (ajuste a URL do seu serviço):

   BODY='{"reference_id":"ORDER-XYZ-123","status":"PAID"}'
   SIG=$(python3 - <<'PY'
import hmac,hashlib,os,sys
secret=b"teste123"
body=b'{"reference_id":"ORDER-XYZ-123","status":"PAID"}'
print(hmac.new(secret, body, hashlib.sha256).hexdigest())
PY
)

   curl -i -X POST "https://influesafe.onrender.com/webhooks/pagbank" \
     -H "Content-Type: application/json" \
     -H "X-PagBank-Signature: $SIG" \
     --data "$BODY"

3) Antes de testar, crie uma linha em 'purchases' com provider_ref='ORDER-XYZ-123',
   user_id=<um usuário real>, package=10, status='pending'.
   (Isso já acontece naturalmente quando VOCÊ integrar o botão de compra para
   criar o checkout no provider e gravar a purchase.)

4) Se estiver 'pending', o webhook acima marca 'paid' e credita +10.
   Ele é idempotente: se enviar de novo, não duplica crédito.
"""
