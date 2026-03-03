import os
import streamlit as st
import libsql

@st.cache_resource
def get_conn():
    url = st.secrets.get("TURSO_DATABASE_URL", os.getenv("TURSO_DATABASE_URL"))
    token = st.secrets.get("TURSO_AUTH_TOKEN", os.getenv("TURSO_AUTH_TOKEN"))

    if not url or not token:
        raise RuntimeError("Faltam TURSO_DATABASE_URL e TURSO_AUTH_TOKEN (Secrets do Streamlit ou variáveis de ambiente).")

    conn = libsql.connect("sorg_macrobase.db", sync_url=url, auth_token=token)
    conn.sync()
    return conn

def init_schema(conn, schema_path: str = "schema.sql") -> None:
    # Garante FK ativo no SQLite
    conn.execute("PRAGMA foreign_keys = ON;")

    with open(schema_path, "r", encoding="utf-8") as f:
        sql = f.read()

    # Executa várias instruções SQL de uma vez
    conn.executescript(sql)
    conn.commit()
    conn.sync()
