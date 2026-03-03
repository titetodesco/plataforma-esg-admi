import os
import streamlit as st
import libsql

def _get_secret(name: str) -> str:
    # tenta Streamlit secrets; se não existir, tenta env var
    if name in st.secrets:
        return str(st.secrets[name])
    return os.getenv(name, "")

@st.cache_resource
def get_conn():
    """
    Conexão usando Embedded Replica:
    - Mantém um arquivo local (rápido para leitura)
    - Sincroniza com o Turso
    """
    url = _get_secret("TURSO_DATABASE_URL")
    token = _get_secret("TURSO_AUTH_TOKEN")
    if not url or not token:
        raise RuntimeError("Defina TURSO_DATABASE_URL e TURSO_AUTH_TOKEN em st.secrets ou variáveis de ambiente.")

    # arquivo local (no Streamlit Cloud pode ser efêmero, mas tudo fica seguro no Turso)
    conn = libsql.connect("sorg_macrobase.db", sync_url=url, auth_token=token)
    conn.sync()  # puxa últimas mudanças
    return conn

def init_schema(conn):
    """
    Schema simples e flexível: guarda cada aba da macro-base como tabela TEXT.
    """
    conn.execute("""
    CREATE TABLE IF NOT EXISTS macro_table_meta (
        table_name TEXT PRIMARY KEY,
        updated_at TEXT
    );
    """)
    conn.commit()
