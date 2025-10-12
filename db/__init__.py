import os
from contextlib import contextmanager
from pathlib import Path

DB_URL = os.environ.get("DATABASE_URL", "sqlite:///influe.db")

_IS_PG = DB_URL.startswith("postgresql://") or DB_URL.startswith("postgres://")

if not _IS_PG:
    # ------------------------------
    # Backend: SQLite
    # ------------------------------
    import sqlite3

    def _resolve_sqlite_path(url: str) -> str:
        # Aceita formatos: sqlite:///arquivo.db  |  sqlite:////abs/arquivo.db  |  influe.db
        if url.startswith("sqlite:///"):
            path = url.replace("sqlite:///", "", 1)
        elif url.startswith("sqlite:////"):
            path = url.replace("sqlite:////", "/", 1)
        else:
            path = url
        return path

    SQLITE_PATH = _resolve_sqlite_path(DB_URL)
    Path(SQLITE_PATH).parent.mkdir(parents=True, exist_ok=True)

    def get_connection():
        conn = sqlite3.connect(SQLITE_PATH, timeout=30, isolation_level=None)
        conn.row_factory = sqlite3.Row
        return conn

else:
    # ------------------------------
    # Backend: Postgres (psycopg 3)
    # ------------------------------
    # Observação: o psycopg 3 entende sslmode=require; se houver channel_binding, ele ignora sem erro.
    import psycopg
    from psycopg.rows import dict_row

    def get_connection():
        # Conecta usando a URL do Postgres (Neon)
        # row_factory=dict_row permite acessar colunas por nome: row["col"]
        conn = psycopg.connect(DB_URL, row_factory=dict_row)
        return conn

@contextmanager
def db_cursor():
    conn = get_connection()
    try:
        cursor = conn.cursor()
        yield cursor
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_db():
    """Cria tabelas se não existirem (MVP, sem ORM externo)."""
    # Import local para evitar ciclos
    from .models import DDL
    with db_cursor() as cur:
        for stmt in DDL:
            cur.execute(stmt)
