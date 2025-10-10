# payments/mock.py
from typing import Dict, Any
from db.models import create_purchase, increment_user_credits

class MockProvider:
    """
    Provider fictício para desenvolvimento.
    - Marca a compra como paga imediatamente e credita os créditos.
    - NÃO usar em produção.
    """
    def start_checkout(self, user_id: int, package: int) -> Dict[str, Any]:
        # Tabela de preços (centavos BRL)
        price_table = {10: 2990, 20: 5490, 50: 11990}
        amount = price_table.get(package, 2990)
        pid = create_purchase(user_id=user_id, package=package, amount=amount, status="paid", provider_ref="MOCK-OK")
        increment_user_credits(user_id, package)
        return {"ok": True, "purchase_id": pid, "status": "paid"}
