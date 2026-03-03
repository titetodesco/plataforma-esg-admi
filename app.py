import streamlit as st
from modules.db import get_conn, init_schema
from modules.macrobase_editor import render_macrobase_editor

st.set_page_config(layout="wide")
st.title("SORG ESG - Macro-base Builder (Turso)")

conn = get_conn()
init_schema(conn)  # aplica schema.sql se ainda não existir (CREATE IF NOT EXISTS)

render_macrobase_editor(conn)
