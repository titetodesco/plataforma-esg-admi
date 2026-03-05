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
        raise RuntimeError("Defina TURSO_DATABASE_URL e TURSO_AUTH_TOKEN nos Secrets do Streamlit.")
    conn = libsql.connect("sorg_macrobase.db", sync_url=url, auth_token=token)
    return conn

@st.cache_resource
def get_conn():
    conn = _connect()
    conn.sync()
    return conn

def safe_execute(conn, sql: str, params=None, retries: int = 2):
    params = params or ()
    last_err = None
    for _ in range(retries + 1):
        try:
            return conn.execute(sql, params)
        except Exception as e:
            last_err = e
            msg = str(e).lower()
            if "stream not found" in msg or "hrana" in msg:
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
    safe_execute(conn, "PRAGMA foreign_keys = ON;")
    with open(schema_path, "r", encoding="utf-8") as f:
        sql = f.read()
    # split simples por ';' (ok para nosso schema)
    statements = [s.strip() for s in sql.split(";") if s.strip()]
    for stmt in statements:
        safe_execute(conn, stmt + ";")
    conn.sync()
