# db/init.py
import os
import re
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional, Any

# Detecta Postgres x SQLite
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///influe.db").strip()

def is_postgres() -> bool:
    return DATABASE_URL.startswith(("postgres://", "postgresql://"))

# ---------------------------
# Conexões (psycopg | sqlite)
# ---------------------------
_conn_args: dict[str, Any] = {}

def _ensure_sqlite_path(url: str) -> str:
    # Aceita: sqlite:///arquivo.db | sqlite:////abs/arquivo.db | influe.db
    if url.startswith("sqlite:///"):
        return url.replace("sqlite:///", "", 1)
    if url.startswith("sqlite:////"):
        return url.replace("sqlite:////", "/", 1)
    return url

def get_connection():
    """
    Retorna uma conexão aberta (psycopg ou sqlite3).
    Para Postgres: autocommit desabilitado; commit/rollback feito em db_cursor().
    """
    if is_postgres():
        import psycopg
        from psycopg.rows import dict_row

        # Neon precisa de sslmode=require; já vem na URL
        conn = psycopg.connect(DATABASE_URL, row_factory=dict_row, **_conn_args)
        return conn
    else:
        import sqlite3

        path = _ensure_sqlite_path(DATABASE_URL)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(path, timeout=30, isolation_level=None)
        conn.row_factory = sqlite3.Row
        # Para trabalhar em transação explícita no cursor manager:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        return conn

@contextmanager
def db_cursor():
    """
    Context manager que abre conexão + cursor e faz commit/rollback seguro.
    Usa transação explícita em ambos os bancos.
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        # Inicia transação
        if is_postgres():
            # psycopg já inicia transação na primeira operação
            pass
        else:
            # sqlite: BEGIN IMMEDIATE para evitar write-locks
            conn.execute("BEGIN")
        yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        try:
            cur.close()
        except Exception:
            pass
        conn.close()

# ---------------------------
# Helpers SQL (placeholders)
# ---------------------------
def qp(sql: str) -> str:
    """
    Converte placeholders estilo SQLite ('?') para Postgres ('%s') quando necessário.
    """
    if is_postgres():
        return sql.replace("?", "%s")
    return sql

# ---------------------------
# DDL
# ---------------------------
DDL_STATEMENTS = [
    # users
    """
    CREATE TABLE IF NOT EXISTS users (
        id              SERIAL PRIMARY KEY,
        email           TEXT UNIQUE NOT NULL,
        password_hash   TEXT NOT NULL,
        credits_remaining INTEGER DEFAULT 0,
        created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """,
    # sessions (créditos temporários por sessão)
    """
    CREATE TABLE IF NOT EXISTS sessions (
        session_id              TEXT PRIMARY KEY,
        ip_hash                 TEXT,
        user_agent_hash         TEXT,
        credits_temp_remaining  INTEGER DEFAULT 0,
        created_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """,
    # analyses (histórico)
    """
    CREATE TABLE IF NOT EXISTS analyses (
        id          SERIAL PRIMARY KEY,
        session_id  TEXT,
        user_id     INTEGER,
        type        TEXT NOT NULL,
        meta        TEXT,
        score_risk  INTEGER DEFAULT 0,
        tags        TEXT,
        created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """,
    # purchases (futuro uso / mock)
    """
    CREATE TABLE IF NOT EXISTS purchases (
        id           SERIAL PRIMARY KEY,
        user_id      INTEGER NOT NULL,
        package      INTEGER NOT NULL,
        amount       NUMERIC DEFAULT 0,
        status       TEXT,
        provider_ref TEXT,
        created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """,
]

def _adapt_ddl_for_sqlite(sql: str) -> str:
    if is_postgres():
        return sql
    # Ajustes de compatibilidade mínimos para SQLite
    sql = re.sub(r"\bSERIAL\b", "INTEGER", sql, flags=re.I)
    sql = sql.replace("NUMERIC", "REAL")
    sql = sql.replace("TIMESTAMP DEFAULT CURRENT_TIMESTAMP", "DATETIME DEFAULT CURRENT_TIMESTAMP")
    return sql

def init_db():
    """
    Cria as tabelas se não existirem. Idempotente.
    """
    with db_cursor() as cur:
        for stmt in DDL_STATEMENTS:
            cur.execute(_adapt_ddl_for_sqlite(stmt))
