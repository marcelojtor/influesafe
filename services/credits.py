import os
from typing import Optional, Tuple
from db.models import (
    get_or_create_session,
    consume_session_credit_atomic,
    consume_user_credit_atomic,
)

FREE_CREDITS = int(os.environ.get("FREE_CREDITS", "3"))

def ensure_temp_session(session_id: str, ip_hash: str, ua_hash: str) -> None:
    get_or_create_session(session_id=session_id, ip_hash=ip_hash, ua_hash=ua_hash, free_credits=FREE_CREDITS)

def consume_credit(user_id: Optional[int], session_id: Optional[str]) -> bool:
    """
    Consome 1 crédito do usuário autenticado; se não houver, tenta da sessão temporária.
    Retorna True se conseguiu consumir; False caso contrário.
    """
    if user_id:
        ok = consume_user_credit_atomic(user_id)
        if ok:
            return True
    if session_id:
        return consume_session_credit_atomic(session_id)
    return False
