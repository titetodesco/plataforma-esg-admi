import streamlit as st
import pandas as pd
from utils.excel_io import load_macrobase

def render_macrobase_editor(conn):
    st.header("Macro-base (Turso)")

    st.subheader("1) Upload da Macro-base (Excel)")
    uploaded_file = st.file_uploader("Carregar arquivo MACRO_BASE.xlsx", type=["xlsx"])

    if uploaded_file:
        data = load_macrobase(uploaded_file)

        if st.button("Publicar macro-base no Turso (schema relacional)"):
            with st.spinner("Gravando no Turso..."):
                publish_macrobase_relacional(conn, data)
            st.success("Macro-base publicada no Turso!")

        st.divider()
        st.subheader("Pré-visualização do Excel carregado")
        for k in ["EIXOS","TEMAS","TOPICOS","INDICADORES","VARIAVEIS","INDICADOR_VARIAVEL"]:
            st.write(f"**{k}**")
            st.dataframe(data[k], use_container_width=True)

    st.divider()
    st.subheader("2) Visualizar macro-base no Turso (tabelas reais)")

    tabs = st.tabs(["eixo","tema","topico","indicador","variavel","indicador_variavel"])
    for tab, table in zip(tabs, ["eixo","tema","topico","indicador","variavel","indicador_variavel"]):
        with tab:
            try:
                df = load_table_df(conn, table)
                st.dataframe(df, use_container_width=True)
            except Exception as e:
                st.info(f"Não consegui ler a tabela '{table}'. Detalhe: {e}")

def publish_macrobase_relacional(conn, data: dict):
    conn.execute("PRAGMA foreign_keys = ON;")

    # 1) apagar na ordem correta (filhos -> pais)
    conn.execute("DELETE FROM indicador_variavel;")
    conn.execute("DELETE FROM indicador;")
    conn.execute("DELETE FROM topico;")
    conn.execute("DELETE FROM tema;")
    conn.execute("DELETE FROM eixo;")
    conn.execute("DELETE FROM variavel;")
    conn.commit()

    # 2) inserir EIXOS
    df = data["EIXOS"].fillna("")
    for _, r in df.iterrows():
        conn.execute(
            "INSERT INTO eixo (eixo_id, codigo, nome, descricao, peso_default) VALUES (?,?,?,?,?)",
            (
                str(r["EIXO_ID"]).strip(),
                str(r["EIXO_ID"]).strip(),
                str(r["NOME"]).strip(),
                str(r.get("DESCRICAO","")).strip(),
                float(r.get("PESO_DEFAULT") or 0),
            ),
        )

    # 3) inserir TEMAS
    df = data["TEMAS"].fillna("")
    for _, r in df.iterrows():
        conn.execute(
            "INSERT INTO tema (tema_id, eixo_id, codigo, nome, descricao, peso_default) VALUES (?,?,?,?,?,?)",
            (
                str(r["TEMA_ID"]).strip(),
                str(r["EIXO_ID"]).strip(),
                str(r.get("CODIGO") or r["TEMA_ID"]).strip(),
                str(r["NOME"]).strip(),
                str(r.get("DESCRICAO","")).strip(),
                float(r.get("PESO_DEFAULT") or 0),
            ),
        )

    # 4) inserir TOPICOS
    df = data["TOPICOS"].fillna("")
    for _, r in df.iterrows():
        conn.execute(
            "INSERT INTO topico (topico_id, tema_id, codigo, nome, descricao, is_default) VALUES (?,?,?,?,?,?)",
            (
                str(r["TOPICO_ID"]).strip(),
                str(r["TEMA_ID"]).strip(),
                str(r.get("CODIGO") or r["TOPICO_ID"]).strip(),
                str(r["NOME"]).strip(),
                str(r.get("DESCRICAO","")).strip(),
                0,
            ),
        )

    # 5) inserir INDICADORES  (IMPORTANTE: precisa de TOPICO_ID no excel)
    df = data["INDICADORES"].fillna("")
    for _, r in df.iterrows():
        conn.execute(
            """
            INSERT INTO indicador
            (indicador_id, topico_id, codigo, nome, descricao, unidade, tipo_resposta, tipo_indicador, formula, peso_default)
            VALUES (?,?,?,?,?,?,?,?,?,?)
            """,
            (
                str(r["INDICADOR_ID"]).strip(),
                str(r["TOPICO_ID"]).strip(),     # <- aqui é o ponto-chave
                str(r.get("CODIGO") or r["INDICADOR_ID"]).strip(),
                str(r["NOME"]).strip(),
                str(r.get("DESCRICAO","")).strip(),
                str(r.get("UNIDADE","")).strip(),
                str(r.get("TIPO_RESPOSTA","MULTIPLA")).strip(),
                "SIMPLES",
                str(r.get("FORMULA","")).strip(),
                float(r.get("PESO_DEFAULT") or 0),
            ),
        )

    # 6) inserir VARIAVEIS
    df = data["VARIAVEIS"].fillna("")
    for _, r in df.iterrows():
        conn.execute(
            """
            INSERT INTO variavel
            (variavel_id, codigo, nome, descricao, unidade, tipo_dado, tipo_resposta, opcoes_json, valor_ref_min, valor_ref_max)
            VALUES (?,?,?,?,?,?,?,?,?,?)
            """,
            (
                str(r["VARIAVEL_ID"]).strip(),
                str(r.get("CODIGO") or r["VARIAVEL_ID"]).strip(),
                str(r["NOME"]).strip(),
                str(r.get("DESCRICAO","")).strip(),
                str(r.get("UNIDADE","")).strip(),
                str(r.get("TIPO_DADO","TEXTO")).strip(),
                str(r.get("TIPO_RESPOSTA","TEXTO")).strip(),
                str(r.get("OPCOES_JSON") or r.get("OPCOES") or "").strip(),
                r.get("VALOR_REF_MIN") if r.get("VALOR_REF_MIN") != "" else None,
                r.get("VALOR_REF_MAX") if r.get("VALOR_REF_MAX") != "" else None,
            ),
        )

    # 7) inserir INDICADOR_VARIAVEL
    df = data["INDICADOR_VARIAVEL"].fillna("")
    for _, r in df.iterrows():
        conn.execute(
            "INSERT INTO indicador_variavel (indicador_id, variavel_id, papel, obrigatoria) VALUES (?,?,?,?)",
            (
                str(r["INDICADOR_ID"]).strip(),
                str(r["VARIAVEL_ID"]).strip(),
                str(r.get("PAPEL","ENTRADA")).strip().upper(),
                int(r.get("OBRIGATORIA") or 0),
            ),
        )

    conn.commit()
    conn.sync()

def load_table_df(conn, table: str) -> pd.DataFrame:
    cur = conn.execute(f"SELECT * FROM {table};")
    rows = cur.fetchall()
    cols = [d[0] for d in cur.description] if cur.description else []
    return pd.DataFrame(rows, columns=cols)
