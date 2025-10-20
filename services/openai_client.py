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
    _HAS_OPENAI = True
except Exception:
    _HAS_OPENAI = False
    OpenAI = object  # type: ignore


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
    s = (s or "").strip()
    # remove blocos de markdown ```json ... ```
    if s.startswith("```"):
        parts = s.split("```")
        for chunk in parts:
            chunk = (chunk or "").strip()
            if chunk.startswith("json"):
                chunk = chunk[4:].strip()
            if chunk.startswith("{") and chunk.endswith("}"):
                s = chunk
                break
    try:
        data = json.loads(s)
    except Exception:
        # fallback simples mas seguro
        preview = s[:240] + ("..." if len(s) > 240 else "")
        return {
            "summary": preview or "Análise concluída.",
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
    """
    Versão resiliente:
    - Nunca levanta exceção para o chamador (app.py): sempre retorna dict {ok: bool, ...}.
    - Se faltar OPENAI_API_KEY ou lib, funciona em modo MOCK se MOCK_AI=1; caso contrário,
      retorna erro amigável.
    - Compatível com app.py: analyze_image aceita **kwargs (instruction/intention).
    """

    def __init__(self):
        self.api_key = os.environ.get("OPENAI_API_KEY", "").strip()
        self.vision_model = os.environ.get("OPENAI_VISION_MODEL", "gpt-4o-mini")
        self.text_model = os.environ.get("OPENAI_TEXT_MODEL", "gpt-4o-mini")
        # tempo máximo por chamada (segurança)
        self.request_timeout_s = float(os.environ.get("OPENAI_TIMEOUT_S", "30"))
        # pequenas retentativas
        self.retries = int(os.environ.get("OPENAI_RETRIES", "2"))
        self.retry_backoff_s = float(os.environ.get("OPENAI_BACKOFF_S", "1.2"))
        # modo mock (para validar fluxo sem crédito)
        self.mock = os.environ.get("MOCK_AI", "").lower() in ("1", "true", "yes", "on")

        self.client = None
        if _HAS_OPENAI and self.api_key and not self.mock:
            try:
                self.client = OpenAI(api_key=self.api_key)
            except Exception:
                # mantém None; chamadas retornarão erro amigável
                self.client = None

    # -----------------------------------------------------
    # Helpers de mock
    # -----------------------------------------------------
    @staticmethod
    def _ok(payload: Dict[str, Any]) -> Dict[str, Any]:
        payload.setdefault("ok", True)
        return payload

    @staticmethod
    def _err(msg: str) -> Dict[str, Any]:
        return {"ok": False, "error": msg}

    def _mock_image(self, instruction: Optional[str]) -> Dict[str, Any]:
        recs: List[str] = [
            "Ajuste iluminação e contraste.",
            "Evite fundo com ruído visual.",
            "Inclua legenda objetiva com CTA."
        ]
        if instruction:
            recs.insert(0, f"Considere a intenção do usuário: “{instruction}”.")
        return self._ok({
            "summary": "Análise simulada (mock). A imagem parece adequada para redes sociais.",
            "score_risk": 12,
            "tags": ["mock", "preview", "teste"],
            "recommendations": recs
        })

    def _mock_text(self, text: str) -> Dict[str, Any]:
        risky = 5 if len(text or "") < 200 else 15
        return self._ok({
            "summary": "Análise simulada (mock). O texto está claro e objetivo.",
            "score_risk": risky,
            "tags": ["mock", "copywriting", "preview"],
            "recommendations": [
                "Revise ortografia e pontuação.",
                "Destaque um benefício concreto.",
                "Inclua uma chamada para ação clara."
            ]
        })

    # -----------------------------------------------------
    # Análise de IMAGEM
    # -----------------------------------------------------
    def analyze_image(self, filepath: str, **kwargs) -> Dict[str, Any]:
        """
        Lê a imagem local -> base64 -> envia ao modelo multimodal -> retorna dicionário padronizado.
        Aceita kwargs (instruction/intent) para compatibilidade com o app.py.
        """
        # normaliza instrução/intenção (se vier do app)
        instruction = kwargs.get("instruction")
        if instruction is None:
            instruction = kwargs.get("intent")

        # Modo mock se ativado ou se não houver SDK/chave/cliente
        if self.mock or not _HAS_OPENAI or not self.api_key or self.client is None:
            return self._mock_image(instruction)

        # lê imagem
        try:
            with open(filepath, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("ascii")
        except Exception as e:
            return self._err(f"Falha ao ler imagem: {e}")

        user_instruction = (
            "Analise esta imagem para publicação em redes sociais. Avalie riscos, privacidade e reputação. "
            "Responda estritamente no JSON especificado."
        )
        if instruction:
            user_instruction += f"\nIntenção do usuário: {instruction}"

        # Monta mensagens no formato chat (image_url com data URL base64)
        content = [
            {"type": "text", "text": user_instruction},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}" }},
        ]

        last_err: Optional[Exception] = None
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
                text = (resp.choices[0].message.content or "").strip()
                data = _safe_parse_model_json(text)
                return self._ok({
                    "summary": data["summary"],
                    "score_risk": data["score_risk"],
                    "tags": data["tags"],
                    "recommendations": data["recommendations"],
                })
            except Exception as e:
                last_err = e
                if attempt < self.retries:
                    time.sleep(self.retry_backoff_s)
                else:
                    return self._err(f"OpenAI (image) falhou: {last_err}")

        return self._err("Falha desconhecida na análise de imagem.")

    # -----------------------------------------------------
    # Análise de TEXTO
    # -----------------------------------------------------
    def analyze_text(self, text: str) -> Dict[str, Any]:
        # Modo mock se ativado ou se não houver SDK/chave/cliente
        if self.mock or not _HAS_OPENAI or not self.api_key or self.client is None:
            return self._mock_text(text)

        user_instruction = (
            "Analise o texto para publicação em redes sociais. Avalie riscos, privacidade, tom e reputação. "
            "Responda estritamente no JSON especificado."
        )

        last_err: Optional[Exception] = None
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
                out = (resp.choices[0].message.content or "").strip()
                data = _safe_parse_model_json(out)
                return self._ok({
                    "summary": data["summary"],
                    "score_risk": data["score_risk"],
                    "tags": data["tags"],
                    "recommendations": data["recommendations"],
                })
            except Exception as e:
                last_err = e
                if attempt < self.retries:
                    time.sleep(self.retry_backoff_s)
                else:
                    return self._err(f"OpenAI (text) falhou: {last_err}")

        return self._err("Falha desconhecida na análise de texto.")
