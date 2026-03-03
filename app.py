import streamlit as st
from modules.macrobase_editor import render_macrobase_editor

st.set_page_config(layout="wide")
st.title("SORG ESG - Macro-base Builder (Turso)")

menu = st.sidebar.selectbox("Menu", ["Macro-base"])

if menu == "Macro-base":
    render_macrobase_editor()
