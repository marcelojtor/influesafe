from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from werkzeug.utils import secure_filename
import os

# --- Config ---
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-influe')
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(__file__), 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB por arquivo

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# --- Rotas ---
@app.route('/')
def home():
    # credits_left poderia vir do banco; aqui, placeholder
    credits_left = 3
    return render_template('index.html', credits_left=credits_left)

@app.route('/login')
def login():
    # Placeholder simples — tela real virá depois
    return jsonify({"status": "ok", "message": "Tela de login será implementada."}), 200

@app.route('/signup')
def signup():
    return jsonify({"status": "ok", "message": "Tela de cadastro será implementada."}), 200

@app.route('/upload/photo', methods=['POST'])
def upload_photo():
    if 'photo' not in request.files:
        return jsonify({"ok": False, "error": "Nenhuma foto enviada."}), 400
    file = request.files['photo']
    if file.filename == '':
        return jsonify({"ok": False, "error": "Arquivo inválido."}), 400

    filename = secure_filename(file.filename)
    save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(save_path)

    # TODO: Integrar com OpenAI Vision e retornar análise
    return jsonify({
        "ok": True,
        "message": "Foto recebida com sucesso. A análise de IA será integrada em seguida.",
        "filename": filename
    }), 200

@app.route('/upload/text', methods=['POST'])
def upload_text():
    text_content = None

    # Prioridade 1: arquivo .txt (ou similar)
    upfile = request.files.get('textfile')
    if upfile and upfile.filename:
        text_content = upfile.read().decode('utf-8', errors='ignore')

    # Prioridade 2: conteúdo digitado
    if not text_content:
        text_content = request.form.get('textcontent', '').strip()

    if not text_content:
        return jsonify({"ok": False, "error": "Nenhum texto fornecido."}), 400

    # TODO: Integrar com OpenAI para análise de texto
    return jsonify({
        "ok": True,
        "message": "Texto recebido com sucesso. A análise de IA será integrada em seguida.",
        "chars": len(text_content)
    }), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
