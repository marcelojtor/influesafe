from dataclasses import dataclass
from typing import Optional, List

# DDL das tabelas (MVP)
DDL = [
    """
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        credits_remaining INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS sessions (
        session_id TEXT PRIMARY KEY,
        ip_hash TEXT,
        ua_hash TEXT,
        credits_temp_remaining INTEGER NOT NULL DEFAULT 0,
        migrated_user_id INTEGER,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS analyses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        session_id TEXT,
        type TEXT NOT NULL,          -- 'photo' | 'text'
        meta TEXT,                   -- JSON string (MVP)
        score_risk INTEGER,          -- 0..100
        tags TEXT,                   -- CSV ou JSON (MVP)
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS purchases (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        package INTEGER NOT NULL,    -- 10, 20, 50
        amount INTEGER NOT NULL,     -- centavos BRL (MVP)
        status TEXT NOT NULL,        -- 'pending' | 'paid' | 'failed'
        provider_ref TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );
    """,
]

# Helpers de domínio (dataclasses opcionais)
@dataclass
class User:
    id: int
    email: str
    credits_remaining: int

@dataclass
class SessionTemp:
    session_id: str
    credits_temp_remaining: int

# Funções CRUD minimalistas
from . import db_cursor

def get_or_create_session(session_id: str, ip_hash: str, ua_hash: str, free_credits: int = 3):
    with db_cursor() as cur:
        cur.execute("SELECT session_id, credits_temp_remaining FROM sessions WHERE session_id = ?", (session_id,))
        row = cur.fetchone()
        if row:
            return SessionTemp(session_id=row["session_id"], credits_temp_remaining=row["credits_temp_remaining"])
        cur.execute(
            "INSERT INTO sessions (session_id, ip_hash, ua_hash, credits_temp_remaining) VALUES (?,?,?,?)",
            (session_id, ip_hash, ua_hash, free_credits),
        )
        return SessionTemp(session_id=session_id, credits_temp_remaining=free_credits)

def get_user_by_email(email: str) -> Optional[User]:
    with db_cursor() as cur:
        cur.execute("SELECT id, email, credits_remaining FROM users WHERE email = ?", (email,))
        r = cur.fetchone()
        if not r:
            return None
        return User(id=r["id"], email=r["email"], credits_remaining=r["credits_remaining"])

def create_user(email: str, password_hash: str, credits: int = 0) -> int:
    with db_cursor() as cur:
        cur.execute(
            "INSERT INTO users (email, password_hash, credits_remaining) VALUES (?,?,?)",
            (email, password_hash, credits),
        )
        return cur.lastrowid

def increment_user_credits(user_id: int, amount: int):
    with db_cursor() as cur:
        cur.execute("UPDATE users SET credits_remaining = credits_remaining + ?, updated_at = datetime('now') WHERE id = ?", (amount, user_id))

def consume_user_credit_atomic(user_id: int) -> bool:
    with db_cursor() as cur:
        cur.execute("SELECT credits_remaining FROM users WHERE id = ? FOR UPDATE", (user_id,))
        row = cur.fetchone()
        if not row or row["credits_remaining"] <= 0:
            return False
        cur.execute("UPDATE users SET credits_remaining = credits_remaining - 1, updated_at = datetime('now') WHERE id = ?", (user_id,))
        return True

def consume_session_credit_atomic(session_id: str) -> bool:
    with db_cursor() as cur:
        cur.execute("SELECT credits_temp_remaining FROM sessions WHERE session_id = ? FOR UPDATE", (session_id,))
        row = cur.fetchone()
        if not row or row["credits_temp_remaining"] <= 0:
            return False
        cur.execute("UPDATE sessions SET credits_temp_remaining = credits_temp_remaining - 1 WHERE session_id = ?", (session_id,))
        return True

def record_analysis(user_id: Optional[int], session_id: Optional[str], a_type: str, meta: str, score_risk: int, tags: str):
    with db_cursor() as cur:
        cur.execute(
            "INSERT INTO analyses (user_id, session_id, type, meta, score_risk, tags) VALUES (?,?,?,?,?,?)",
            (user_id, session_id, a_type, meta, score_risk, tags),
        )

def create_purchase(user_id: int, package: int, amount: int, status: str, provider_ref: str):
    with db_cursor() as cur:
        cur.execute(
            "INSERT INTO purchases (user_id, package, amount, status, provider_ref) VALUES (?,?,?,?,?)",
            (user_id, package, amount, status, provider_ref),
        )
        return cur.lastrowid

def update_purchase_status(purchase_id: int, status: str):
    with db_cursor() as cur:
        cur.execute("UPDATE purchases SET status = ? WHERE id = ?", (status, purchase_id))
