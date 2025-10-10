from __future__ import annotations
import os
import uuid
import json
import hashlib
from datetime import datetime, timedelta
from flask import (
    Flask, render_template, request, jsonify, make_response, send_from_directory
)
from werkzeug.utils import secure_filename

# --- Config & Extensions ---
from db import db, init_db
from db.models import User, SessionTemp, Analysis, Purchase, with_transaction
from utils.security import (
    hash_password, verify_password, make_jwt_for_user, require_auth_maybe
)
from utils.rate_limit import rate_limit
from services.credits import (
    get_or_create_session, get_credits_status, consume_credit_atomic, migrate_session_to_user
)
from services.openai_client import analyze_photo_with_ai, analyze_text_with_ai
from payments import get_payment_provider

# App
app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-influe")
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///influe.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Políticas / Operação
FREE_CREDITS = int(os.environ.get("FREE_CREDITS", "3"))
FREE_CREDITS_COOLDOWN_HOURS = int(os.environ.get("FREE_CREDITS_COOLDOWN_HOURS", "24"))
MAX_UPLOAD_MB = int(os.environ.get("MAX_UPLOAD_MB", "4"))
TEMP_RETENTION_DAYS = int(os.environ.get("TEMP_RETENTION_DAYS", "7"))
RATE_LIMIT_PER_MINUTE = int(os.environ.get("RATE_LIMIT_PER_MINUTE", "6"))
RATE_LIMIT_MIN_INTERVAL_MS = int(os.environ.get("RATE_LIMIT_MIN_INTERVAL_MS", "1000"))

# Uploads
BASE_DIR = os.path.dirname(__file__)
STORAGE_DIR = os.path.join(BASE_DIR, "storage", "temp")
os.makedirs(STORAGE_DIR, exist_ok=True)

# Init DB
init_db(app)


# -----------------------------
# Helpers
# -----------------------------
def _ip_hash():
    ip = request.headers.get("X-Forwarded-For", request.remote_addr) or ""
    return hashlib.sha256(ip.encode()).hexdigest()

def _ua_hash():
    ua = request.headers.get("User-Agent", "") + "|" + request.headers.get("Accept", "")
    return hashlib.sha256(ua.encode()).hexdigest()

def _session_id_from_cookie() -> str | None:
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


# -----------------------------
# Rotas Web (home/landing)
# -----------------------------
@app.route("/")
def home():
    # Mantém sua homepage existente (templates/index.html)
    credits_left = 3
    return render_template("index.html", credits_left=credits_left)

@app.route("/privacy")
def privacy():
    return jsonify({
        "ok": True,
        "policy": "Dados minimizados, imagens temporárias por até {} dias, créditos por sessão e por usuário. Consulte README para detalhes LGPD.".format(TEMP_RETENTION_DAYS)
    })

@app.route("/health")
def health():
    return jsonify({"status": "ok", "time": datetime.utcnow().isoformat()})


# -----------------------------
# Status de créditos (sessão vs usuário)
# -----------------------------
@app.route("/credits_status", methods=["GET"])
def credits_status():
    session_id = _session_id_from_cookie()
    status = get_credits_status(session_id=session_id)
    return jsonify({"ok": True, "data": status})


# -----------------------------
# Auth simples (email + senha)
# -----------------------------
@app.post("/auth/register")
def auth_register():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    if not email or not password:
        return jsonify({"ok": False, "error": "Email e senha são obrigatórios."}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({"ok": False, "error": "Email já cadastrado."}), 409

    user = User(email=email, password_hash=hash_password(password))
    db.session.add(user)
    db.session.commit()

    # migrar créditos de sessão (se houver)
    session_id = _session_id_from_cookie()
    if session_id:
        migrate_session_to_user(session_id=session_id, user_id=user.id)

    token = make_jwt_for_user(user.id, app.config["SECRET_KEY"])
    return jsonify({"ok": True, "token": token, "user_id": user.id})

@app.post("/auth/login")
def auth_login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    if not email or not password:
        return jsonify({"ok": False, "error": "Email e senha são obrigatórios."}), 400

    user = User.query.filter_by(email=email).first()
    if not user or not verify_password(password, user.password_hash):
        return jsonify({"ok": False, "error": "Credenciais inválidas."}), 401

    token = make_jwt_for_user(user.id, app.config["SECRET_KEY"])
    return jsonify({"ok": True, "token": token, "user_id": user.id})

@app.get("/user/profile")
@require_auth_maybe
def user_profile(user_id: int | None):
    # Retorna histórico de análises pagas (se logado)
    if not user_id:
        return jsonify({"ok": True, "data": {"logged_in": False, "history": []}})

    analyses = (
        Analysis.query.filter(Analysis.user_id == user_id)
        .order_by(Analysis.created_at.desc()).limit(50).all()
    )
    history = [
        {
            "id": a.id,
            "type": a.type,
            "score_risk": a.score_risk,
            "tags": json.loads(a.tags_json or "[]"),
            "created_at": a.created_at.isoformat()
        }
        for a in analyses
    ]
    user = User.query.get(user_id)
    return jsonify({
        "ok": True,
        "data": {
            "logged_in": True,
            "credits_remaining": user.credits_remaining,
            "history": history
        }
    })


# -----------------------------
# Analyze Photo / Text
# -----------------------------
def _ensure_session():
    session_id = _session_id_from_cookie()
    if not session_id:
        session_id = str(uuid.uuid4())
        ip_h = _ip_hash()
        ua_h = _ua_hash()
        get_or_create_session(session_id, ip_h, ua_h, FREE_CREDITS, FREE_CREDITS_COOLDOWN_HOURS)
    return session_id

@app.post("/analyze_photo")
@rate_limit(RATE_LIMIT_PER_MINUTE, RATE_LIMIT_MIN_INTERVAL_MS)
@require_auth_maybe
def analyze_photo(user_id: int | None):
    # Garante sessão e bloqueios
    session_id = _ensure_session()

    # Validação & armazenamento temporário
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

    # Consumo de crédito atômico + análise
    try:
        with with_transaction():
            ok = consume_credit_atomic(user_id=user_id, session_id=session_id)
            if not ok:
                return jsonify({"ok": False, "error": "Sem créditos disponíveis. Faça login e/ou compre créditos."}), 402

            # Chama a IA
            result = analyze_photo_with_ai(save_path)

            # Pós-processamento e persistência básica
            analysis = Analysis(
                session_id=session_id,
                user_id=user_id,
                type="photo",
                meta_json=json.dumps({"filename": filename}),
                score_risk=result.get("score_risk", 0),
                tags_json=json.dumps(result.get("tags", [])),
                created_at=datetime.utcnow(),
            )
            db.session.add(analysis)
        # fim da transação

        return jsonify({"ok": True, "analysis": result})
    except Exception as e:
        app.logger.exception("Erro em analyze_photo")
        return jsonify({"ok": False, "error": "Falha ao processar a imagem."}), 500

@app.post("/analyze_text")
@rate_limit(RATE_LIMIT_PER_MINUTE, RATE_LIMIT_MIN_INTERVAL_MS)
@require_auth_maybe
def analyze_text(user_id: int | None):
    session_id = _ensure_session()
    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip()
    if not text:
        return jsonify({"ok": False, "error": "Texto vazio."}), 400

    try:
        with with_transaction():
            ok = consume_credit_atomic(user_id=user_id, session_id=session_id)
            if not ok:
                return jsonify({"ok": False, "error": "Sem créditos disponíveis. Faça login e/ou compre créditos."}), 402

            result = analyze_text_with_ai(text)

            analysis = Analysis(
                session_id=session_id,
                user_id=user_id,
                type="text",
                meta_json=json.dumps({"chars": len(text)}),
                score_risk=result.get("score_risk", 0),
                tags_json=json.dumps(result.get("tags", [])),
                created_at=datetime.utcnow(),
            )
            db.session.add(analysis)

        return jsonify({"ok": True, "analysis": result})
    except Exception:
        app.logger.exception("Erro em analyze_text")
        return jsonify({"ok": False, "error": "Falha ao processar o texto."}), 500


# -----------------------------
# Pagamentos (Mock + PagSeguro)
# -----------------------------
@app.post("/purchase")
@require_auth_maybe
def purchase(user_id: int | None):
    if not user_id:
        return jsonify({"ok": False, "error": "É necessário login para comprar créditos."}), 401
    data = request.get_json(silent=True) or {}
    package = int(data.get("package") or 10)  # 10, 20, 50
    provider = get_payment_provider()
    checkout = provider.create_checkout(user_id=user_id, package=package)
    return jsonify({"ok": True, "checkout": checkout})

@app.post("/webhook/pagseguro")
def webhook_pagseguro():
    provider = get_payment_provider()
    try:
        payload = request.get_json(force=True)
    except Exception:
        return jsonify({"ok": False, "error": "Payload inválido."}), 400

    if not provider.verify_webhook(payload, request.headers):
        return jsonify({"ok": False, "error": "Assinatura inválida."}), 401

    credits, user_id, provider_ref = provider.parse_webhook(payload)
    if not credits or not user_id:
        return jsonify({"ok": False, "error": "Webhook incompleto."}), 400

    with with_transaction():
        user = User.query.get(user_id)
        if not user:
            return jsonify({"ok": False, "error": "Usuário não encontrado."}), 404
        user.credits_remaining = (user.credits_remaining or 0) + credits
        p = Purchase(
            user_id=user_id,
            package=credits,
            amount=0,  # mock
            status="paid",
            provider_ref=provider_ref,
            created_at=datetime.utcnow(),
        )
        db.session.add(p)

    return jsonify({"ok": True})


# -----------------------------
# Rota para servir arquivos temporários (debug/local)
# -----------------------------
@app.route("/storage/temp/<session_id>/<path:fname>")
def serve_temp(session_id, fname):
    return send_from_directory(os.path.join(STORAGE_DIR, session_id), fname)


# -----------------------------
# Boot
# -----------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
