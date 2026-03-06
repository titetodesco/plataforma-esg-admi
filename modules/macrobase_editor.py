import streamlit as st
import pandas as pd
from utils.excel_io import load_macrobase


def _bump_cache_ver():
    st.session_state["_cache_ver"] = int(st.session_state.get("_cache_ver", 0)) + 1


def _w_1a10(x):
    try:
        v = int(float(str(x).replace(",", ".")))
    except Exception:
        v = 1
    return max(1, min(10, v))


def _render_crud_eixo(conn):
    st.markdown("### CRUD Eixo (MVP)")

    eixos = load_table_df(conn, "eixo")
    if eixos.empty:
        eixos = pd.DataFrame(columns=["eixo_id", "codigo", "nome", "descricao", "peso_default"])

    eixos = eixos[["eixo_id", "codigo", "nome", "descricao", "peso_default"]].copy()

    with st.form("crud_eixo_form"):
        eixos_edit = st.data_editor(
            eixos,
            hide_index=True,
            use_container_width=True,
            column_config={
                "eixo_id": st.column_config.TextColumn("eixo_id", disabled=True),
                "peso_default": st.column_config.NumberColumn("peso_default", min_value=1, max_value=10, step=1),
            },
            key="crud_eixo_editor",
        )
        save_eixos = st.form_submit_button("Salvar alterações de Eixos")

    if save_eixos:
        for _, r in eixos_edit.iterrows():
            conn.execute(
                """
                UPDATE eixo
                SET codigo=?, nome=?, descricao=?, peso_default=?
                WHERE eixo_id=?
                """,
                (
                    str(r.get("codigo", "") or "").strip(),
                    str(r.get("nome", "") or "").strip(),
                    str(r.get("descricao", "") or "").strip(),
                    _w_1a10(r.get("peso_default", 1)),
                    str(r["eixo_id"]).strip(),
                ),
            )
        conn.commit()
        _bump_cache_ver()
        st.success("Eixos atualizados.")

    st.markdown("#### Novo Eixo")
    c1, c2, c3 = st.columns(3)
    with c1:
        new_eixo_id = st.text_input("eixo_id", key="new_eixo_id")
    with c2:
        new_eixo_codigo = st.text_input("codigo", key="new_eixo_codigo")
    with c3:
        new_eixo_peso = st.number_input("peso_default", min_value=1, max_value=10, step=1, value=1, key="new_eixo_peso")
    new_eixo_nome = st.text_input("nome", key="new_eixo_nome")
    new_eixo_desc = st.text_area("descricao", key="new_eixo_desc")

    if st.button("Criar Eixo"):
        if not new_eixo_id.strip() or not new_eixo_nome.strip():
            st.error("Informe pelo menos eixo_id e nome.")
        else:
            conn.execute(
                """
                INSERT INTO eixo (eixo_id, codigo, nome, descricao, peso_default)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    new_eixo_id.strip(),
                    (new_eixo_codigo.strip() or new_eixo_id.strip()),
                    new_eixo_nome.strip(),
                    new_eixo_desc.strip(),
                    _w_1a10(new_eixo_peso),
                ),
            )
            conn.commit()
            _bump_cache_ver()
            st.success("Eixo criado.")

    if not eixos.empty:
        eixo_del = st.selectbox("Excluir eixo_id", eixos["eixo_id"].tolist(), key="del_eixo_id")
        if st.button("Excluir Eixo"):
            conn.execute("DELETE FROM eixo WHERE eixo_id=?", (eixo_del,))
            conn.commit()
            _bump_cache_ver()
            st.success(f"Eixo {eixo_del} excluído.")


def _render_crud_tema(conn):
    st.markdown("### CRUD Tema (MVP)")

    temas = load_table_df(conn, "tema")
    if temas.empty:
        temas = pd.DataFrame(columns=["tema_id", "eixo_id", "codigo", "nome", "descricao", "peso_default"])

    temas = temas[["tema_id", "eixo_id", "codigo", "nome", "descricao", "peso_default"]].copy()

    with st.form("crud_tema_form"):
        temas_edit = st.data_editor(
            temas,
            hide_index=True,
            use_container_width=True,
            column_config={
                "tema_id": st.column_config.TextColumn("tema_id", disabled=True),
                "peso_default": st.column_config.NumberColumn("peso_default", min_value=1, max_value=10, step=1),
            },
            key="crud_tema_editor",
        )
        save_temas = st.form_submit_button("Salvar alterações de Temas")

    if save_temas:
        for _, r in temas_edit.iterrows():
            conn.execute(
                """
                UPDATE tema
                SET eixo_id=?, codigo=?, nome=?, descricao=?, peso_default=?
                WHERE tema_id=?
                """,
                (
                    str(r.get("eixo_id", "") or "").strip(),
                    str(r.get("codigo", "") or "").strip(),
                    str(r.get("nome", "") or "").strip(),
                    str(r.get("descricao", "") or "").strip(),
                    _w_1a10(r.get("peso_default", 1)),
                    str(r["tema_id"]).strip(),
                ),
            )
        conn.commit()
        _bump_cache_ver()
        st.success("Temas atualizados.")

    eixos = load_table_df(conn, "eixo")
    eixo_opts = eixos["eixo_id"].tolist() if not eixos.empty else []

    st.markdown("#### Novo Tema")
    t1, t2, t3 = st.columns(3)
    with t1:
        new_tema_id = st.text_input("tema_id", key="new_tema_id")
    with t2:
        new_tema_codigo = st.text_input("codigo tema", key="new_tema_codigo")
    with t3:
        new_tema_peso = st.number_input("peso_default tema", min_value=1, max_value=10, step=1, value=1, key="new_tema_peso")

    if eixo_opts:
        new_tema_eixo = st.selectbox("eixo_id do tema", eixo_opts, key="new_tema_eixo")
    else:
        new_tema_eixo = ""
        st.warning("Crie pelo menos um eixo antes de criar tema.")

    new_tema_nome = st.text_input("nome tema", key="new_tema_nome")
    new_tema_desc = st.text_area("descricao tema", key="new_tema_desc")

    if st.button("Criar Tema"):
        if not new_tema_id.strip() or not new_tema_nome.strip() or not new_tema_eixo.strip():
            st.error("Informe tema_id, eixo_id e nome do tema.")
        else:
            conn.execute(
                """
                INSERT INTO tema (tema_id, eixo_id, codigo, nome, descricao, peso_default)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    new_tema_id.strip(),
                    new_tema_eixo.strip(),
                    (new_tema_codigo.strip() or new_tema_id.strip()),
                    new_tema_nome.strip(),
                    new_tema_desc.strip(),
                    _w_1a10(new_tema_peso),
                ),
            )
            conn.commit()
            _bump_cache_ver()
            st.success("Tema criado.")

    if not temas.empty:
        tema_del = st.selectbox("Excluir tema_id", temas["tema_id"].tolist(), key="del_tema_id")
        if st.button("Excluir Tema"):
            conn.execute("DELETE FROM tema WHERE tema_id=?", (tema_del,))
            conn.commit()
            _bump_cache_ver()
            st.success(f"Tema {tema_del} excluído.")


def _render_crud_macrobase(conn):
    st.subheader("Manutenção da Macro-base (CRUD inicial)")
    st.caption("MVP inicial com CRUD de Eixo e Tema. Podemos evoluir para Tópico, Indicador e Variável na próxima etapa.")

    tab_eixo, tab_tema = st.tabs(["Eixos", "Temas"])
    with tab_eixo:
        _render_crud_eixo(conn)
    with tab_tema:
        _render_crud_tema(conn)


def render_macrobase_editor(conn):
    st.header("Macro-base (Turso) — v2.1")

    tab_planilha, tab_crud = st.tabs(["Carga via planilha", "CRUD Macro-base (MVP)"])

    with tab_planilha:
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
                _bump_cache_ver()
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

    with tab_crud:
        _render_crud_macrobase(conn)

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
