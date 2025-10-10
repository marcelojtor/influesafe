# payments/__init__.py
import os

_PROVIDER = os.environ.get("PAYMENT_PROVIDER", "mock").strip().lower()

def get_payment_provider():
    """
    Retorna a implementação do provedor de pagamento conforme variável de ambiente.
    - mock (default): credita imediatamente (desenvolvimento).
    - pagseguro: stub seguro (a implementar).
    """
    if _PROVIDER == "pagseguro":
        from .pagseguro import PagSeguroProvider
        return PagSeguroProvider()
    # default -> mock
    from .mock import MockProvider
    return MockProvider()
