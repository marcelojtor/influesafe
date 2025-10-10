# payments/pagseguro.py
from typing import Dict, Any

class PagSeguroProvider:
    """
    Stub do PagSeguro.
    - Em produção: implementar criação de checkout, validação de assinatura e webhook.
    """
    def start_checkout(self, user_id: int, package: int) -> Dict[str, Any]:
        return {
            "ok": False,
            "error": "PagSeguroProvider.start_checkout não implementado nesta branch (stub)."
        }

    # Exemplo de placeholder para futura validação:
    def validate_webhook(self, headers, body_bytes) -> Dict[str, Any]:
        return {
            "ok": False,
            "error": "PagSeguroProvider.validate_webhook não implementado nesta branch (stub)."
        }
