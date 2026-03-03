import streamlit as st
import pandas as pd
from utils.excel_io import load_macrobase
from modules.db import get_conn, init_schema

def _safe_ident(name: str) -> str:
    # nomes simples pra tabela: só letras/números/underscore
    return "".join(ch if ch.isalnum() else "_" for ch in name).upper()

def _ensure_table(conn, table_name: str, df: pd.DataFrame):
    # cria tabela com colunas TEXT baseadas no dataframe
    cols = []
    for c in df.columns:
        col = _safe_ident(str(c))
        cols.append(f'"{col}" TEXT')
    cols_sql = ", ".join(cols) if cols else '"_EMPTY" TEXT'
    conn.execute(f'CREATE TABLE IF NOT EXISTS "{table_name}" ({cols_sql});')
    conn.commit()

def _replace_table_data(conn, table_name: str, df: pd.DataFrame):
    # estratégia simples: apaga e reinsere (bom para macro-base que você “publica” por versão)
    conn.execute(f'DELETE FROM "{table_name}";')
    conn.commit()

    if df.empty:
        return

    cols = [_safe_ident(str(c)) for c in df.columns]
    col_sql = ", ".join([f'"{c}"' for c in cols])
    ph = ", ".join(["?"] * len(cols))

    sql = f'INSERT INTO "{table_name}" ({col_sql}) VALUES ({ph});'
    for row in df.itertuples(index=False, name=None):
        conn.execute(sql, [None if (isinstance(v, float) and pd.isna(v)) else str(v) for v in row])
    conn.commit()

def _load_table_df(conn, table_name: str) -> pd.DataFrame:
    # lê tudo da tabela e devolve DF
    cur = conn.execute(f'SELECT * FROM "{table_name}";')
    rows = cur.fetchall()
    cols = [d[0] for d in cur.description] if cur.description else []
    return pd.DataFrame(rows, columns=cols)

def render_macrobase_editor(conn):
    st.header("Macro-base (Turso)")

    conn = get_conn()
    init_schema(conn)

    st.subheader("1) Upload da Macro-base (Excel)")
    uploaded_file = st.file_uploader("Carregar arquivo MACRO_BASE.xlsx", type=["xlsx"])

    if uploaded_file:
        data = load_macrobase(uploaded_file)

        if st.button("Publicar macro-base no Turso (substitui tabelas)"):
            with st.spinner("Gravando no Turso..."):
                for sheet_name, df in data.items():
                    table_name = f"MB_{_safe_ident(sheet_name)}"
                    _ensure_table(conn, table_name, df)
                    _replace_table_data(conn, table_name, df)
                conn.sync()  # sobe alterações
            st.success("Macro-base publicada no Turso!")

    st.divider()
    st.subheader("2) Visualizar macro-base carregada (lendo do Turso)")

    tabs = st.tabs(["EIXOS", "TEMAS", "TOPICOS", "INDICADORES", "VARIAVEIS", "INDICADOR_VARIAVEL"])
    for tab, name in zip(tabs, ["EIXOS","TEMAS","TOPICOS","INDICADORES","VARIAVEIS","INDICADOR_VARIAVEL"]):
        with tab:
            table_name = f"MB_{_safe_ident(name)}"
            try:
                conn.sync()  # puxa últimas mudanças
                df = _load_table_df(conn, table_name)
                st.dataframe(df, use_container_width=True)
            except Exception as e:
                st.info(f"Tabela {table_name} ainda não existe no Turso. Faça o upload e publique. Detalhe: {e}")
