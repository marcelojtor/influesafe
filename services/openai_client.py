# services/openai_client.py
# INFLUE — Cliente OpenAI (multimodal, texto+imagem)
# Requisitos: pip install openai
# Variáveis de ambiente:
#   - OPENAI_API_KEY           (obrigatória)
#   - OPENAI_VISION_MODEL      (opcional; padrão: gpt-4o-mini)
#   - OPENAI_TEXT_MODEL        (opcional; padrão: gpt-4o-mini)

import os
import time
import json
import base64
from typing import Any, Dict, List, Optional

# OpenAI SDK moderno
try:
    from openai import OpenAI
except Exception:
    # fallback nome antigo do pacote (caso o deploy use versão anterior)
    from openai import OpenAI  # type: ignore


_SYSTEM_PROMPT_IMAGE = (
    "Você é um analista de imagem especializado em reputação, privacidade e risco de engajamento nas redes sociais. "
    "Analise a imagem recebida (conteúdo visual geral, estética, contexto implícito) e responda EM JSON puro, SEM comentários, no formato:\n"
    "{\n"
    '  "summary": "1 a 3 frases objetivas sobre o que a imagem comunica e possíveis implicações",\n'
    '  "score_risk": 0-100,  // 0 baixo risco, 100 altíssimo risco\n'
    '  "tags": ["palavras-chave", "..."],\n'
    '  "recommendations": ["até 5 recomendações curtas e acionáveis"]\n'
    "}\n"
    "Considere privacidade (rostos, placas, documentos), sinais de controvérsia, brand safety e possíveis leituras equivocadas. "
    "Se não tiver contexto suficiente, assuma um cenário neutro e aponte incertezas."
)

_SYSTEM_PROMPT_TEXT = (
    "Você é um analista de conteúdo textual especializado em reputação, privacidade e risco de engajamento nas redes sociais. "
    "Analise o texto e responda EM JSON puro, SEM comentários, no formato:\n"
    "{\n"
    '  "summary": "1 a 3 frases objetivas sobre o conteúdo e implicações",\n'
    '  "score_risk": 0-100,\n'
    '  "tags": ["palavras-chave", "..."],\n'
    '  "recommendations": ["até 5 recomendações curtas e acionáveis"]\n'
    "}\n"
    "Considere: sensibilidade do tema, tom, possíveis leituras ambíguas, privacidade e brand safety."
)


def _coerce_int(v: Any, default: int = 0) -> int:
    try:
        i = int(v)
        if i < 0:
            return 0
        if i > 100:
            return 100
        return i
    except Exception:
        return default


def _safe_parse_model_json(s: str) -> Dict[str, Any]:
    """
    Tenta extrair um JSON válido da resposta do modelo.
    Se falhar, cria um fallback mínimo para não quebrar o app.
    """
    s = s.strip()
    # remove blocos de markdown ```json ... ```
    if s.startswith("```"):
        # tenta encontrar o trecho entre os fences
        parts = s.split("```")
        # algo como: ["", "json\n{...}", ""]
        for chunk in parts:
            chunk = chunk.strip()
            if chunk.startswith("json"):
                chunk = chunk[4:].strip()
            if chunk.startswith("{") and chunk.endswith("}"):
                s = chunk
                break
    try:
        data = json.loads(s)
    except Exception:
        # fallback muito simples
        return {
            "summary": s[:240] + ("..." if len(s) > 240 else ""),
            "score_risk": 50,
            "tags": [],
            "recommendations": [],
        }
    # saneamento mínimo
    out = {
        "summary": data.get("summary") or "",
        "score_risk": _coerce_int(data.get("score_risk"), 50),
        "tags": data.get("tags") or [],
        "recommendations": data.get("recommendations") or [],
    }
    # garante tipos
    if not isinstance(out["tags"], list):
        out["tags"] = [str(out["tags"])]
    if not isinstance(out["recommendations"], list):
        out["recommendations"] = [str(out["recommendations"])]
    if not isinstance(out["summary"], str):
        out["summary"] = str(out["summary"])
    return out


class OpenAIClient:
    def __init__(self):
        api_key = os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY não configurada.")
        self.client = OpenAI(api_key=api_key)

        self.vision_model = os.environ.get("OPENAI_VISION_MODEL", "gpt-4o-mini")
        self.text_model = os.environ.get("OPENAI_TEXT_MODEL", "gpt-4o-mini")

        # tempo máximo por chamada (segurança)
        self.request_timeout_s = float(os.environ.get("OPENAI_TIMEOUT_S", "30"))

        # pequenas retentativas
        self.retries = 2
        self.retry_backoff_s = 1.2

    # -----------------------------------------------------
    # Análise de IMAGEM
    # -----------------------------------------------------
    def analyze_image(self, filepath: str) -> Dict[str, Any]:
        """
        Lê a imagem local -> base64 -> envia ao modelo multimodal -> retorna dicionário padronizado.
        """
        try:
            with open(filepath, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("ascii")
        except Exception as e:
            return {"ok": False, "error": f"Falha ao ler imagem: {e}"}

        user_instruction = (
            "Analise esta imagem para publicação em redes sociais. Avalie riscos, privacidade e reputação. "
            "Responda estritamente no JSON especificado."
        )

        # Monta mensagens no formato chat (com input_image em base64 data URL)
        content = [
            {"type": "text", "text": user_instruction},
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{b64}"}
            },
        ]

        last_err = None
        for attempt in range(self.retries + 1):
            try:
                resp = self.client.chat.completions.create(
                    model=self.vision_model,
                    messages=[
                        {"role": "system", "content": _SYSTEM_PROMPT_IMAGE},
                        {"role": "user", "content": content},
                    ],
                    temperature=0.2,
                    max_tokens=600,
                    timeout=self.request_timeout_s,
                )
                text = resp.choices[0].message.content or ""
                data = _safe_parse_model_json(text)
                return {
                    "ok": True,
                    "summary": data["summary"],
                    "score_risk": data["score_risk"],
                    "tags": data["tags"],
                    "recommendations": data["recommendations"],
                }
            except Exception as e:
                last_err = e
                if attempt < self.retries:
                    time.sleep(self.retry_backoff_s)
                else:
                    return {"ok": False, "error": f"OpenAI (image) falhou: {last_err}"}

        return {"ok": False, "error": "Falha desconhecida na análise de imagem."}

    # -----------------------------------------------------
    # Análise de TEXTO
    # -----------------------------------------------------
    def analyze_text(self, text: str) -> Dict[str, Any]:
        """
        Envia apenas texto ao modelo -> retorna dicionário padronizado.
        """
        user_instruction = (
            "Analise o texto para publicação em redes sociais. Avalie riscos, privacidade, tom e reputação. "
            "Responda estritamente no JSON especificado."
        )

        last_err = None
        for attempt in range(self.retries + 1):
            try:
                resp = self.client.chat.completions.create(
                    model=self.text_model,
                    messages=[
                        {"role": "system", "content": _SYSTEM_PROMPT_TEXT},
                        {"role": "user", "content": f"{user_instruction}\n\nTexto:\n{text}"},
                    ],
                    temperature=0.2,
                    max_tokens=600,
                    timeout=self.request_timeout_s,
                )
                out = resp.choices[0].message.content or ""
                data = _safe_parse_model_json(out)
                return {
                    "ok": True,
                    "summary": data["summary"],
                    "score_risk": data["score_risk"],
                    "tags": data["tags"],
                    "recommendations": data["recommendations"],
                }
            except Exception as e:
                last_err = e
                if attempt < self.retries:
                    time.sleep(self.retry_backoff_s)
                else:
                    return {"ok": False, "error": f"OpenAI (text) falhou: {last_err}"}

        return {"ok": False, "error": "Falha desconhecida na análise de texto."}
