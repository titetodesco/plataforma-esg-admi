import streamlit as st
import pandas as pd
from utils.excel_io import load_macrobase

def render_macrobase_editor(conn):
    st.header("Macro-base (Turso) — v2.1")

    uploaded_file = st.file_uploader("Carregar arquivo MACRO_BASE_v2_1.xlsx", type=["xlsx"])

    if uploaded_file:
        data = load_macrobase(uploaded_file)

        st.subheader("Pré-visualização do Excel")
        for k in data.keys():
            st.write(f"**{k}**")
            st.dataframe(data[k], width="stretch")

        if st.button("Publicar macro-base no Turso (schema v2.1)"):
            with st.spinner("Gravando no Turso..."):
                publish_macrobase_relacional_v21(conn, data)
            st.success("Macro-base publicada no Turso! ✅")

    st.divider()
    st.subheader("Visualização das tabelas no Turso")
    for table in ["eixo","tema","topico","indicador","variavel","variavel_opcao","indicador_variavel"]:
        with st.expander(table, expanded=False):
            try:
                df = load_table_df(conn, table)
                st.dataframe(df, width="stretch")
            except Exception as e:
                st.info(f"Não consegui ler {table}: {e}")

def publish_macrobase_relacional_v21(conn, data: dict):
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.sync()

    # helpers
    def sid(x): return str(x).strip() if x is not None else ""
    def stext(x): return "" if pd.isna(x) else str(x).strip()

    # PESO_DEFAULT: inteiro 1..10; vazio vira 1
    def sint_1a10(x):
        if x is None or x == "" or (isinstance(x, float) and pd.isna(x)):
            return 1
        try:
            v = int(float(str(x).replace(",", ".")))
        except Exception:
            return 1
        return max(1, min(10, v))

    # limpa na ordem correta
    conn.execute("DELETE FROM indicador_variavel;")
    conn.execute("DELETE FROM variavel_opcao;")
    conn.execute("DELETE FROM variavel;")
    conn.execute("DELETE FROM indicador;")
    conn.execute("DELETE FROM topico;")
    conn.execute("DELETE FROM tema;")
    conn.execute("DELETE FROM eixo;")
    conn.commit()

    # EIXOS
    df = data["EIXOS"].fillna("")
    for _, r in df.iterrows():
        conn.execute(
            "INSERT INTO eixo (eixo_id,codigo,nome,descricao,peso_default) VALUES (?,?,?,?,?)",
            (sid(r["EIXO_ID"]), sid(r.get("CODIGO") or r["EIXO_ID"]), stext(r["NOME"]), stext(r.get("DESCRICAO","")), sint_1a10(r.get("PESO_DEFAULT")))
        )

    # TEMAS
    df = data["TEMAS"].fillna("")
    for _, r in df.iterrows():
        conn.execute(
            "INSERT INTO tema (tema_id,eixo_id,codigo,nome,descricao,peso_default) VALUES (?,?,?,?,?,?)",
            (sid(r["TEMA_ID"]), sid(r["EIXO_ID"]), sid(r.get("CODIGO") or r["TEMA_ID"]), stext(r["NOME"]), stext(r.get("DESCRICAO","")), sint_1a10(r.get("PESO_DEFAULT")))
        )

    # TOPICOS
    df = data["TOPICOS"].fillna("")
    for _, r in df.iterrows():
        # Se sua planilha não tiver PESO_DEFAULT em TOPICOS, cai para 1
        conn.execute(
            "INSERT INTO topico (topico_id,tema_id,codigo,nome,descricao,peso_default) VALUES (?,?,?,?,?,?)",
            (sid(r["TOPICO_ID"]), sid(r["TEMA_ID"]), sid(r.get("CODIGO") or r["TOPICO_ID"]), stext(r["NOME"]), stext(r.get("DESCRICAO","")), sint_1a10(r.get("PESO_DEFAULT")))
        )

    # INDICADORES (sem tipo_resposta)
    df = data["INDICADORES"].fillna("")
    for _, r in df.iterrows():
        conn.execute(
            """INSERT INTO indicador
               (indicador_id,topico_id,codigo,nome,descricao,tipo_indicador,psr_tipo,formula,unidade_resultado,peso_default)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                sid(r["INDICADOR_ID"]),
                sid(r["TOPICO_ID"]),
                sid(r.get("CODIGO") or r["INDICADOR_ID"]),
                stext(r["NOME"]),
                stext(r.get("DESCRICAO","")),
                sid(r.get("TIPO_INDICADOR","DIRETO")),
                sid(r.get("PSR_TIPO","")) or None,
                stext(r.get("FORMULA","")),
                stext(r.get("UNIDADE_RESULTADO","")),
                sint_1a10(r.get("PESO_DEFAULT")),
            )
        )

    # VARIAVEIS (perguntas)
    df = data["VARIAVEIS"].fillna("")
    for _, r in df.iterrows():
        conn.execute(
            """INSERT INTO variavel
               (variavel_id,codigo,pergunta_texto,descricao,tipo_resposta,unidade_entrada,observacoes)
               VALUES (?,?,?,?,?,?,?)""",
            (
                sid(r["VARIAVEL_ID"]),
                sid(r.get("CODIGO") or r["VARIAVEL_ID"]),
                stext(r["PERGUNTA_TEXTO"]),
                stext(r.get("DESCRICAO","")),
                sid(r["TIPO_RESPOSTA"]),
                stext(r.get("UNIDADE_ENTRADA","")),
                stext(r.get("OBSERVACOES","")),
            )
        )

    # VARIAVEL_OPCOES
    df = data["VARIAVEL_OPCOES"].fillna("")
    for _, r in df.iterrows():
        conn.execute(
            "INSERT INTO variavel_opcao (variavel_id,ordem,texto_opcao,score_1a5) VALUES (?,?,?,?)",
            (sid(r["VARIAVEL_ID"]), int(r["ORDEM"]), stext(r["TEXTO_OPCAO"]), int(r["SCORE_1A5"]))
        )

    # INDICADOR_VARIAVEL
    df = data["INDICADOR_VARIAVEL"].fillna("")
    for _, r in df.iterrows():
        peso = r.get("PESO")
        peso = None if (peso is None or peso == "" or pd.isna(peso)) else sint_1a10(peso)
        conn.execute(
            """INSERT INTO indicador_variavel
               (indicador_id,variavel_id,papel,obrigatoria,peso)
               VALUES (?,?,?,?,?)""",
            (
                sid(r["INDICADOR_ID"]),
                sid(r["VARIAVEL_ID"]),
                sid(r.get("PAPEL","ENTRADA")),
                int(r.get("OBRIGATORIA") or 1),
                peso,
            )
        )

    conn.commit()
    conn.sync()

def load_table_df(conn, table: str) -> pd.DataFrame:
    cur = conn.execute(f"SELECT * FROM {table};")
    rows = cur.fetchall()
    cols = [d[0] for d in cur.description] if cur.description else []
    return pd.DataFrame(rows, columns=cols)
