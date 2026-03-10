import streamlit as st
from modules.db import get_conn, init_schema
from modules.macrobase_editor import render_macrobase_editor
from modules.setup_builder import render_setup_builder

st.set_page_config(layout="wide")
st.title("SORG ESG - Builder (Turso)")

try:
    conn = get_conn()
    init_schema(conn)
except Exception as e:
    st.error("Falha ao conectar no Turso.")
    st.info(
        "No Streamlit Cloud, configure em **Manage app → Settings → Secrets** "
        "os campos de URL e token do Turso."
    )
    st.code(
        'TURSO_DATABASE_URL = "libsql://SEU-BANCO.turso.io"\n'
        'TURSO_AUTH_TOKEN = "SEU_TOKEN"\n\n'
        '[turso]\n'
        'database_url = "libsql://SEU-BANCO.turso.io"\n'
        'auth_token = "SEU_TOKEN"',
        language="toml",
    )
    st.caption(f"Detalhe técnico: {e}")
    st.stop()

menu = st.sidebar.selectbox("Menu", ["Macro-base", "Setup do Questionário"])

if menu == "Macro-base":
    render_macrobase_editor(conn)

if menu == "Setup do Questionário":
    render_setup_builder(conn)
