from typing import Dict, Any

class PagSeguroProvider:
    """
    Stub seguro do provider PagSeguro.
    Ao integrar de fato:
      - iniciar checkout (sessão, ref de pagamento)
      - validar assinatura do webhook
      - atualizar compra e créditos em transação
    """
    def start_checkout(self, user_id: int, package: int) -> Dict[str, Any]:
        return {
            "ok": False,
            "error": "PagSeguroProvider.start_checkout não implementado nesta branch (stub)."
        }

    # Exemplo de placeholder: validar webhook
    def validate_webhook(self, headers, body_bytes) -> Dict[str, Any]:
        return {
            "ok": False,
            "error": "PagSeguroProvider.validate_webhook não implementado nesta branch (stub)."
        }
