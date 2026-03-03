import os
import streamlit as st
import libsql

@st.cache_resource
def get_conn():
    url = st.secrets["TURSO_DATABASE_URL"]
    token = st.secrets["TURSO_AUTH_TOKEN"]
    conn = libsql.connect("sorg_macrobase.db", sync_url=url, auth_token=token)
    conn.sync()
    return conn

def init_schema(conn, schema_path: str = "schema.sql") -> None:
    # Importante: ligar FK no SQLite
    conn.execute("PRAGMA foreign_keys = ON;")

    with open(schema_path, "r", encoding="utf-8") as f:
        sql = f.read()

    # libsql aceita executar múltiplas instruções via executescript
    # (se sua versão não tiver, eu te mando alternativa com split seguro)
    conn.executescript(sql)

    conn.commit()
    conn.sync()
