import os
import time
import streamlit as st
import libsql

def _get_secret(name: str) -> str:
    if name in st.secrets:
        return str(st.secrets[name])
    return os.getenv(name, "")

def _connect():
    url = _get_secret("TURSO_DATABASE_URL")
    token = _get_secret("TURSO_AUTH_TOKEN")
    if not url or not token:
        raise RuntimeError("Defina TURSO_DATABASE_URL e TURSO_AUTH_TOKEN nos Secrets do Streamlit (ou env vars).")

    # embedded replica local (ok mesmo no Streamlit Cloud)
    conn = libsql.connect("sorg_macrobase.db", sync_url=url, auth_token=token)
    return conn

@st.cache_resource
def get_conn():
    conn = _connect()
    conn.sync()
    return conn

def safe_execute(conn, sql: str, params=None, retries: int = 2):
    """
    Executa SQL e, se o Hrana 'stream not found' ocorrer,
    recria a conexão (limpando cache) e tenta de novo.
    """
    params = params or ()
    last_err = None

    for attempt in range(retries + 1):
        try:
            return conn.execute(sql, params)
        except Exception as e:
            last_err = e
            msg = str(e).lower()
            if "stream not found" in msg or "hrana" in msg:
                # recria conexão
                try:
                    st.cache_resource.clear()
                except Exception:
                    pass
                time.sleep(0.2)
                conn = get_conn()
                continue
            raise

    raise last_err

def init_schema(conn, schema_path: str = "schema.sql") -> None:
    # garante FK on (via safe_execute)
    safe_execute(conn, "PRAGMA foreign_keys = ON;")

    with open(schema_path, "r", encoding="utf-8") as f:
        sql = f.read()

    # executescript pode falhar dependendo da lib; fazemos split simples por ';'
    statements = [s.strip() for s in sql.split(";") if s.strip()]
    for stmt in statements:
        safe_execute(conn, stmt + ";")

    conn.sync()
