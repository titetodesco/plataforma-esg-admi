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
        "No Streamlit Cloud, configure em **Manage app → Settings → Secrets**: "
        "`TURSO_DATABASE_URL` e `TURSO_AUTH_TOKEN`."
    )
    st.caption(f"Detalhe técnico: {e}")
    st.stop()

menu = st.sidebar.selectbox("Menu", ["Macro-base", "Setup do Questionário"])

if menu == "Macro-base":
    render_macrobase_editor(conn)

if menu == "Setup do Questionário":
    render_setup_builder(conn)
