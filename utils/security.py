import hashlib
import os
import secrets
from typing import Tuple

def hash_ip(ip: str) -> str:
    return hashlib.sha256(ip.encode("utf-8")).hexdigest()

def hash_ua(ua: str) -> str:
    return hashlib.sha256(ua.encode("utf-8")).hexdigest()

# Hash de senha com PBKDF2 (sem dependências externas)
def hash_password(password: str, salt: str = None) -> Tuple[str, str]:
    salt = salt or secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100_000)
    return salt, dk.hex()

def verify_password(password: str, salt: str, hashed_hex: str) -> bool:
    _, check = hash_password(password, salt)
    return secrets.compare_digest(check, hashed_hex)
