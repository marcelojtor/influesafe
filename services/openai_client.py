import os
import time
from typing import Dict, Any

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL_VISION", "gpt-5-vision")
OPENAI_TIMEOUT = int(os.environ.get("OPENAI_TIMEOUT_SECONDS", "10"))

class OpenAIClient:
    """
    Cliente de IA (stub seguro).
    - Em produção: integrar chamada real à API.
    - Sem chave: retorna análise sintética para não quebrar o fluxo.
    """

    def analyze_image(self, file_path: str) -> Dict[str, Any]:
        if not OPENAI_API_KEY:
            # Stub: simula latência e resposta estruturada
            time.sleep(0.5)
            return {
                "ok": True,
                "score_risk": 38,
                "tags": ["ambiente_publico", "marca_visivel_baixa"],
                "summary": "A imagem parece adequada; baixo risco reputacional.",
                "recommendations": [
                    "Verifique direitos de imagem se houver logotipos.",
                    "Ajuste ligeiramente a iluminação para destacar o rosto.",
                    "Use uma legenda objetiva e positiva."
                ],
            }

        # TODO: Implementar chamada real (quando autorizado)
        # Dica: use timeouts e trate exceções para retornar fallback amigável.
        # Exemplo (pseudocódigo):
        # from openai import OpenAI
        # client = OpenAI(api_key=OPENAI_API_KEY, base_url=os.getenv("OPENAI_API_BASE"))
        # resp = client.images.analyze( ... )
        # return mapear_resp(resp)
        return {
            "ok": False,
            "error": "Integração real com OpenAI ainda não habilitada nesta branch.",
        }

    def analyze_text(self, text: str) -> Dict[str, Any]:
        if not OPENAI_API_KEY:
            time.sleep(0.3)
            lower = text.lower()
            score = 20
            tags = []
            if any(w in lower for w in ["ódio", "ofensa", "ataque", "xingar"]):
                score = 72
                tags.append("linguagem_ofensiva")
            if any(w in lower for w in ["álcool", "bebida"]):
                score = max(score, 55)
                tags.append("alcool")
            return {
                "ok": True,
                "score_risk": score,
                "tags": tags or ["neutro"],
                "summary": "Texto analisado com sucesso.",
                "recommendations": [
                    "Mantenha clareza e empatia na mensagem.",
                    "Evite termos ambíguos que possam ser mal interpretados.",
                    "Inclua um call-to-action leve e positivo."
                ],
            }
        return {
            "ok": False,
            "error": "Integração real com OpenAI ainda não habilitada nesta branch.",
        }
