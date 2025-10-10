import os

PROVIDER = os.environ.get("PAYMENT_PROVIDER", "mock").lower()

def get_provider():
    if PROVIDER == "pagseguro":
        from .pagseguro import PagSeguroProvider
        return PagSeguroProvider()
    # default mock
    from .mock import MockProvider
    return MockProvider()
