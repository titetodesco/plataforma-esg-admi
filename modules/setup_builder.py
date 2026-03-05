import streamlit as st
import pandas as pd
from utils.setup_export import export_setup_xlsx

# ---------- helpers ----------
def df_from_query(conn, sql: str, params=()):
    cur = conn.execute(sql, params)
    rows = cur.fetchall()
    cols = [d[0] for d in cur.description] if cur.description else []
    return pd.DataFrame(rows, columns=cols)

def execmany(conn, sql: str, rows):
    for r in rows:
        conn.execute(sql, r)

def normalize_weight(x):
    try:
        v = int(float(str(x).replace(",", ".")))
    except Exception:
        v = 1
    return max(1, min(10, v))

def render_setup_builder(conn):
    st.header("Setup do Questionário (Builder)")

    # ---------------- A) Selecionar / Criar questionário ----------------
    st.subheader("A) Selecionar ou criar questionário (perfil)")
    qdf = df_from_query(conn, """
        SELECT questionario_id, setor, porte, regiao, versao, status, observacao
        FROM questionario
        ORDER BY created_at DESC
    """)

    colA, colB = st.columns([2, 1])
    with colA:
        options = ["(novo)"] + (qdf["questionario_id"].tolist() if not qdf.empty else [])
        selected = st.selectbox("Questionário", options)

    with colB:
        if st.button("Recarregar"):
            st.rerun()

    if selected == "(novo)":
        with st.expander("Criar novo questionário", expanded=True):
            qid = st.text_input("QUESTIONARIO_ID (ex.: QST_DEFAULT, QST_AGRO_PEQ_SUDESTE_v1)")
            setor = st.text_input("Setor (pode ser '*')", value="*")
            porte = st.text_input("Porte (pode ser '*')", value="*")
            regiao = st.text_input("Região (pode ser '*')", value="*")
            versao = st.text_input("Versão", value="v1")
            status = st.selectbox("Status", ["DRAFT", "PUBLISHED", "ARCHIVED"], index=0)
            obs = st.text_input("Observação", value="")

            if st.button("Criar"):
                if not qid.strip():
                    st.error("Informe QUESTIONARIO_ID.")
                    st.stop()

                conn.execute("""
                    INSERT INTO questionario (questionario_id, setor, porte, regiao, versao, status, observacao)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (qid.strip(), setor.strip(), porte.strip(), regiao.strip(), versao.strip(), status, obs.strip()))
                conn.commit()
                conn.sync()
                st.success("Questionário criado.")
                st.rerun()

        st.info("Crie um questionário para habilitar as etapas B–F.")
        return

    qid = selected
    qmeta = df_from_query(conn, """
        SELECT questionario_id, setor, porte, regiao, versao, status, observacao
        FROM questionario WHERE questionario_id = ?
    """, (qid,))
    st.caption(f"Perfil: setor={qmeta.loc[0,'setor']} | porte={qmeta.loc[0,'porte']} | regiao={qmeta.loc[0,'regiao']} | versao={qmeta.loc[0,'versao']} | status={qmeta.loc[0,'status']}")

    st.divider()

    # ---------------- B) Selecionar indicadores + pesos ----------------
    st.subheader("B) Selecionar indicadores e pesos (1..10)")

    # filtros hierárquicos
    eixos = df_from_query(conn, "SELECT eixo_id, nome FROM eixo ORDER BY eixo_id")
    eixo_opt = ["(todos)"] + eixos["eixo_id"].tolist()
    eixo_sel = st.selectbox("Filtro Eixo", eixo_opt)

    temas_sql = """
        SELECT t.tema_id, t.nome
        FROM tema t
        {where}
        ORDER BY t.tema_id
    """
    where = ""
    params = ()
    if eixo_sel != "(todos)":
        where = "WHERE t.eixo_id = ?"
        params = (eixo_sel,)
    temas = df_from_query(conn, temas_sql.format(where=where), params)
    tema_opt = ["(todos)"] + temas["tema_id"].tolist()
    tema_sel = st.selectbox("Filtro Tema", tema_opt)

    topicos_sql = """
        SELECT tp.topico_id, tp.nome
        FROM topico tp
        JOIN tema t ON t.tema_id = tp.tema_id
        {where}
        ORDER BY tp.topico_id
    """
    where = ""
    params = ()
    if tema_sel != "(todos)":
        where = "WHERE tp.tema_id = ?"
        params = (tema_sel,)
    elif eixo_sel != "(todos)":
        where = "WHERE t.eixo_id = ?"
        params = (eixo_sel,)
    topicos = df_from_query(conn, topicos_sql.format(where=where), params)
    topico_opt = ["(todos)"] + topicos["topico_id"].tolist()
    topico_sel = st.selectbox("Filtro Tópico", topico_opt)

    # tabela de indicadores com join no indicador_config
    ind_sql = """
        SELECT
          i.indicador_id,
          i.nome,
          i.tipo_indicador,
          i.psr_tipo,
          i.topico_id,
          COALESCE(ic.ativo, 0) AS ativo,
          COALESCE(ic.peso_indicador, 1) AS peso_indicador
        FROM indicador i
        LEFT JOIN indicador_config ic
          ON ic.indicador_id = i.indicador_id AND ic.questionario_id = ?
        {where}
        ORDER BY i.indicador_id
    """
    where = ""
    params = [qid]
    if topico_sel != "(todos)":
        where = "WHERE i.topico_id = ?"
        params.append(topico_sel)
    elif tema_sel != "(todos)":
        where = "WHERE i.topico_id IN (SELECT topico_id FROM topico WHERE tema_id = ?)"
        params.append(tema_sel)
    elif eixo_sel != "(todos)":
        where = """
        WHERE i.topico_id IN (
          SELECT tp.topico_id FROM topico tp
          JOIN tema t ON t.tema_id = tp.tema_id
          WHERE t.eixo_id = ?
        )
        """
        params.append(eixo_sel)

    ind_df = df_from_query(conn, ind_sql.format(where=where), tuple(params))
    if ind_df.empty:
        st.info("Nenhum indicador encontrado com os filtros atuais.")
    else:
        edit_df = ind_df[["ativo","peso_indicador","indicador_id","nome","tipo_indicador","psr_tipo","topico_id"]].copy()
        edit_df.rename(columns={"peso_indicador":"peso (1..10)"}, inplace=True)

        edited = st.data_editor(
            edit_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "ativo": st.column_config.CheckboxColumn("Ativo"),
                "peso (1..10)": st.column_config.NumberColumn("Peso (1..10)", min_value=1, max_value=10, step=1),
            },
            key=f"ind_editor_{qid}_{eixo_sel}_{tema_sel}_{topico_sel}"
        )

        if st.button("Salvar seleção de indicadores"):
            rows = []
            for _, r in edited.iterrows():
                ativo = 1 if bool(r["ativo"]) else 0
                peso = normalize_weight(r["peso (1..10)"])
                indicador_id = r["indicador_id"]

                # upsert
                conn.execute("""
                    INSERT INTO indicador_config (questionario_id, indicador_id, ativo, peso_indicador)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(questionario_id, indicador_id)
                    DO UPDATE SET ativo=excluded.ativo, peso_indicador=excluded.peso_indicador
                """, (qid, indicador_id, ativo, peso))
            conn.commit()
            conn.sync()
            st.success("Indicadores salvos.")
            st.rerun()

    st.divider()

    # indicadores ativos (para etapas C/D/E)
    active_inds = df_from_query(conn, """
        SELECT i.indicador_id, i.nome, i.tipo_indicador, i.topico_id
        FROM indicador i
        JOIN indicador_config ic ON ic.indicador_id=i.indicador_id
        WHERE ic.questionario_id=? AND ic.ativo=1
        ORDER BY i.indicador_id
    """, (qid,))

    if active_inds.empty:
        st.warning("Nenhum indicador ativo neste questionário. Ative indicadores na etapa B para continuar.")
        return

    # ---------------- C) Pesos por Tema/Tópico ----------------
    st.subheader("C) Pesos por Tema e Tópico (1..10, default=1)")

    # temas/tópicos envolvidos pelos indicadores ativos
    used_topics = df_from_query(conn, """
        SELECT DISTINCT tp.topico_id, tp.nome, tp.tema_id
        FROM topico tp
        JOIN indicador i ON i.topico_id = tp.topico_id
        JOIN indicador_config ic ON ic.indicador_id=i.indicador_id
        WHERE ic.questionario_id=? AND ic.ativo=1
        ORDER BY tp.tema_id, tp.topico_id
    """, (qid,))

    used_themes = df_from_query(conn, """
        SELECT DISTINCT t.tema_id, t.nome, t.eixo_id
        FROM tema t
        JOIN topico tp ON tp.tema_id=t.tema_id
        JOIN indicador i ON i.topico_id=tp.topico_id
        JOIN indicador_config ic ON ic.indicador_id=i.indicador_id
        WHERE ic.questionario_id=? AND ic.ativo=1
        ORDER BY t.eixo_id, t.tema_id
    """, (qid,))

    # carregar pesos existentes, se não existirem, mostrar default 1
    tema_p = df_from_query(conn, """
        SELECT tema_id, peso_tema FROM peso_tema WHERE questionario_id=?
    """, (qid,))
    topico_p = df_from_query(conn, """
        SELECT topico_id, peso_topico FROM peso_topico WHERE questionario_id=?
    """, (qid,))

    tema_map = dict(zip(tema_p["tema_id"], tema_p["peso_tema"])) if not tema_p.empty else {}
    topico_map = dict(zip(topico_p["topico_id"], topico_p["peso_topico"])) if not topico_p.empty else {}

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Pesos por Tema**")
        tedit = used_themes.copy()
        tedit["peso (1..10)"] = tedit["tema_id"].map(lambda x: tema_map.get(x, 1))
        tedit2 = st.data_editor(
            tedit[["tema_id","nome","eixo_id","peso (1..10)"]],
            use_container_width=True,
            hide_index=True,
            column_config={"peso (1..10)": st.column_config.NumberColumn("Peso (1..10)", min_value=1, max_value=10, step=1)},
            key=f"peso_tema_{qid}"
        )

        if st.button("Salvar pesos de Tema"):
            for _, r in tedit2.iterrows():
                conn.execute("""
                    INSERT INTO peso_tema (questionario_id, tema_id, peso_tema)
                    VALUES (?, ?, ?)
                    ON CONFLICT(questionario_id, tema_id)
                    DO UPDATE SET peso_tema=excluded.peso_tema
                """, (qid, r["tema_id"], normalize_weight(r["peso (1..10)"])))
            conn.commit()
            conn.sync()
            st.success("Pesos de tema salvos.")
            st.rerun()

    with col2:
        st.markdown("**Pesos por Tópico**")
        pedit = used_topics.copy()
        pedit["peso (1..10)"] = pedit["topico_id"].map(lambda x: topico_map.get(x, 1))
        pedit2 = st.data_editor(
            pedit[["topico_id","nome","tema_id","peso (1..10)"]],
            use_container_width=True,
            hide_index=True,
            column_config={"peso (1..10)": st.column_config.NumberColumn("Peso (1..10)", min_value=1, max_value=10, step=1)},
            key=f"peso_topico_{qid}"
        )

        if st.button("Salvar pesos de Tópico"):
            for _, r in pedit2.iterrows():
                conn.execute("""
                    INSERT INTO peso_topico (questionario_id, topico_id, peso_topico)
                    VALUES (?, ?, ?)
                    ON CONFLICT(questionario_id, topico_id)
                    DO UPDATE SET peso_topico=excluded.peso_topico
                """, (qid, r["topico_id"], normalize_weight(r["peso (1..10)"])))
            conn.commit()
            conn.sync()
            st.success("Pesos de tópico salvos.")
            st.rerun()

    st.divider()

    # ---------------- D) Faixas de referência ----------------
    st.subheader("D) Faixas de referência (nível 1..5)")
    st.caption("Preencha para indicadores CALCULADOS e/ou quando você quiser mapear valor numérico para score 1..5.")

    # listar indicadores calculados (por ora) – regra simples
    calc_inds = df_from_query(conn, """
        SELECT i.indicador_id, i.nome
        FROM indicador i
        JOIN indicador_config ic ON ic.indicador_id=i.indicador_id
        WHERE ic.questionario_id=? AND ic.ativo=1 AND i.tipo_indicador='CALCULADO'
        ORDER BY i.indicador_id
    """, (qid,))

    if calc_inds.empty:
        st.info("Nenhum indicador CALCULADO ativo. (Você pode adicionar faixas manualmente via SQL depois, se desejar.)")
    else:
        ind_sel = st.selectbox("Escolha um indicador para editar faixas", calc_inds["indicador_id"].tolist())
        faixa = df_from_query(conn, """
            SELECT nivel, tipo_regra, valor_min, valor_max, valor_exato, rotulo
            FROM faixa_referencia
            WHERE questionario_id=? AND indicador_id=?
            ORDER BY nivel
        """, (qid, ind_sel))

        if faixa.empty:
            faixa = pd.DataFrame({
                "nivel":[1,2,3,4,5],
                "tipo_regra":["INTERVALO"]*5,
                "valor_min":[None]*5,
                "valor_max":[None]*5,
                "valor_exato":[None]*5,
                "rotulo":[""]*5
            })

        faixa_edit = st.data_editor(
            faixa,
            use_container_width=True,
            hide_index=True,
            column_config={
                "nivel": st.column_config.NumberColumn("Nível", min_value=1, max_value=5, step=1, disabled=True),
                "tipo_regra": st.column_config.SelectboxColumn("Tipo regra", options=["INTERVALO","EXATO","DIRETO"]),
            },
            key=f"faixa_{qid}_{ind_sel}"
        )

        if st.button("Salvar faixas do indicador"):
            # apagar e inserir 5 níveis (mais simples)
            conn.execute("DELETE FROM faixa_referencia WHERE questionario_id=? AND indicador_id=?", (qid, ind_sel))
            for _, r in faixa_edit.iterrows():
                conn.execute("""
                    INSERT INTO faixa_referencia
                    (questionario_id, indicador_id, nivel, tipo_regra, valor_min, valor_max, valor_exato, rotulo)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    qid, ind_sel, int(r["nivel"]), str(r["tipo_regra"]).strip(),
                    r["valor_min"], r["valor_max"], r["valor_exato"], str(r.get("rotulo","") or "")
                ))
            conn.commit()
            conn.sync()
            st.success("Faixas salvas.")
            st.rerun()

    st.divider()

    # ---------------- E) Recomendações por Tema/Eixo ----------------
    st.subheader("E) Recomendações por nível (Tema / Eixo)")

    # Recomendações por TEMA
    st.markdown("**Recomendações por Tema**")
    tema_sel = st.selectbox("Tema", used_themes["tema_id"].tolist(), key=f"tema_rec_sel_{qid}")
    rec_t = df_from_query(conn, """
        SELECT nivel, recomendacao
        FROM recomendacao_tema
        WHERE questionario_id=? AND tema_id=?
        ORDER BY nivel
    """, (qid, tema_sel))
    if rec_t.empty:
        rec_t = pd.DataFrame({"nivel":[1,2,3,4,5], "recomendacao":[""]*5})

    rec_t_edit = st.data_editor(rec_t, use_container_width=True, hide_index=True,
                                column_config={"nivel": st.column_config.NumberColumn("Nível", disabled=True)},
                                key=f"rec_t_{qid}_{tema_sel}")
    if st.button("Salvar recomendações do Tema"):
        conn.execute("DELETE FROM recomendacao_tema WHERE questionario_id=? AND tema_id=?", (qid, tema_sel))
        for _, r in rec_t_edit.iterrows():
            if str(r["recomendacao"]).strip():
                conn.execute("""
                    INSERT INTO recomendacao_tema (questionario_id, tema_id, nivel, recomendacao)
                    VALUES (?, ?, ?, ?)
                """, (qid, tema_sel, int(r["nivel"]), str(r["recomendacao"]).strip()))
        conn.commit()
        conn.sync()
        st.success("Recomendações do tema salvas.")
        st.rerun()

    st.markdown("---")

    # Recomendações por EIXO (derivados dos temas usados)
    used_eixos = df_from_query(conn, """
        SELECT DISTINCT t.eixo_id
        FROM tema t
        JOIN topico tp ON tp.tema_id=t.tema_id
        JOIN indicador i ON i.topico_id=tp.topico_id
        JOIN indicador_config ic ON ic.indicador_id=i.indicador_id
        WHERE ic.questionario_id=? AND ic.ativo=1
        ORDER BY t.eixo_id
    """, (qid,))
    st.markdown("**Recomendações por Eixo**")
    eixo_sel = st.selectbox("Eixo", used_eixos["eixo_id"].tolist(), key=f"eixo_rec_sel_{qid}")
    rec_e = df_from_query(conn, """
        SELECT nivel, recomendacao
        FROM recomendacao_eixo
        WHERE questionario_id=? AND eixo_id=?
        ORDER BY nivel
    """, (qid, eixo_sel))
    if rec_e.empty:
        rec_e = pd.DataFrame({"nivel":[1,2,3,4,5], "recomendacao":[""]*5})

    rec_e_edit = st.data_editor(rec_e, use_container_width=True, hide_index=True,
                                column_config={"nivel": st.column_config.NumberColumn("Nível", disabled=True)},
                                key=f"rec_e_{qid}_{eixo_sel}")
    if st.button("Salvar recomendações do Eixo"):
        conn.execute("DELETE FROM recomendacao_eixo WHERE questionario_id=? AND eixo_id=?", (qid, eixo_sel))
        for _, r in rec_e_edit.iterrows():
            if str(r["recomendacao"]).strip():
                conn.execute("""
                    INSERT INTO recomendacao_eixo (questionario_id, eixo_id, nivel, recomendacao)
                    VALUES (?, ?, ?, ?)
                """, (qid, eixo_sel, int(r["nivel"]), str(r["recomendacao"]).strip()))
        conn.commit()
        conn.sync()
        st.success("Recomendações do eixo salvas.")
        st.rerun()

    st.divider()

    # ---------------- F) Exportar XLSX ----------------
    st.subheader("F) Exportar SETUP_QUESTIONARIO.xlsx")
    st.caption("Gera o arquivo que será carregado pela outra aplicação para criar o formulário.")

    if st.button("Gerar arquivo SETUP_QUESTIONARIO.xlsx"):
        with st.spinner("Gerando XLSX..."):
            xlsx_bytes = export_setup_xlsx(conn, qid)
        st.download_button(
            "Baixar SETUP_QUESTIONARIO.xlsx",
            data=xlsx_bytes,
            file_name=f"SETUP_QUESTIONARIO_{qid}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
