import streamlit as st
import pandas as pd
from utils.setup_export import export_setup_xlsx

def df_from_query(conn, sql: str, params=()):
    cur = conn.execute(sql, params)
    rows = cur.fetchall()
    cols = [d[0] for d in cur.description] if cur.description else []
    return pd.DataFrame(rows, columns=cols)

def w(x):
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

    options = ["(novo)"] + (qdf["questionario_id"].tolist() if not qdf.empty else [])
    selected = st.selectbox("Questionário", options)

    if selected == "(novo)":
        with st.expander("Criar novo questionário", expanded=True):
            qid = st.text_input("QUESTIONARIO_ID (ex.: QST_DEFAULT)")
            setor = st.text_input("Setor (pode ser '*')", value="*")
            porte = st.text_input("Porte (pode ser '*')", value="*")
            regiao = st.text_input("Região (pode ser '*')", value="*")
            versao = st.text_input("Versão", value="v1")
            status = st.selectbox("Status", ["DRAFT","PUBLISHED","ARCHIVED"], index=0)
            obs = st.text_input("Observação", value="")

            if st.button("Criar"):
                if not qid.strip():
                    st.error("Informe QUESTIONARIO_ID.")
                    st.stop()

                # evita erro de UNIQUE
                exists = df_from_query(conn, "SELECT 1 FROM questionario WHERE questionario_id=? LIMIT 1", (qid.strip(),))
                if not exists.empty:
                    st.warning("Esse QUESTIONARIO_ID já existe. Selecione-o no dropdown.")
                    st.stop()

                conn.execute("""
                    INSERT INTO questionario (questionario_id, setor, porte, regiao, versao, status, observacao)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (qid.strip(), setor.strip(), porte.strip(), regiao.strip(), versao.strip(), status, obs.strip()))
                conn.commit()
                st.success("Questionário criado.")
                st.rerun()

        st.info("Crie um questionário para habilitar as etapas B–F.")
        return

    qid = selected
    qmeta = df_from_query(conn, """
        SELECT questionario_id, setor, porte, regiao, versao, status, observacao
        FROM questionario WHERE questionario_id = ?
    """, (qid,))
    st.caption(
        f"Perfil: setor={qmeta.loc[0,'setor']} | porte={qmeta.loc[0,'porte']} | "
        f"regiao={qmeta.loc[0,'regiao']} | versao={qmeta.loc[0,'versao']} | status={qmeta.loc[0,'status']}"
    )

    st.divider()

    # ---------------- B) Wizard: B1 Temas -> B1.2 Tópicos -> B2 Indicadores ----------------
    st.subheader("B) Seleção (wizard) — Temas → Tópicos → Indicadores")

    tab1, tab2, tab3 = st.tabs(["B1) Temas por Eixo", "B1.2) Tópicos por Tema", "B2) Indicadores por Tópico"])

    # ---------- B1 ----------
    with tab1:
        eixos = df_from_query(conn, "SELECT eixo_id, nome FROM eixo ORDER BY eixo_id")
        eixo_sel = st.selectbox("Eixo", eixos["eixo_id"].tolist(), key=f"b1_eixo_{qid}")

        temas = df_from_query(conn, """
            SELECT tema_id, nome
            FROM tema
            WHERE eixo_id=?
            ORDER BY tema_id
        """, (eixo_sel,))

        # pesos já existentes (ou default 1)
        t_p = df_from_query(conn, "SELECT tema_id, peso_tema FROM peso_tema WHERE questionario_id=?", (qid,))
        t_map = dict(zip(t_p["tema_id"], t_p["peso_tema"])) if not t_p.empty else {}

        tedit = temas.copy()
        tedit["incluir"] = tedit["tema_id"].map(lambda x: x in t_map)
        tedit["peso (1..10)"] = tedit["tema_id"].map(lambda x: int(t_map.get(x, 1)))

        tedit2 = st.data_editor(
            tedit,
            hide_index=True,
            use_container_width=True,
            column_config={
                "incluir": st.column_config.CheckboxColumn("Incluir"),
                "peso (1..10)": st.column_config.NumberColumn("Peso", min_value=1, max_value=10, step=1),
            },
            key=f"b1_temas_editor_{qid}_{eixo_sel}"
        )

        if st.button("Salvar temas do eixo"):
            # remove temas desse eixo do questionário e reinsere os marcados
            conn.execute("""
                DELETE FROM peso_tema
                WHERE questionario_id=?
                  AND tema_id IN (SELECT tema_id FROM tema WHERE eixo_id=?)
            """, (qid, eixo_sel))

            for _, r in tedit2.iterrows():
                if bool(r["incluir"]):
                    conn.execute("""
                        INSERT INTO peso_tema (questionario_id, tema_id, peso_tema)
                        VALUES (?, ?, ?)
                        ON CONFLICT(questionario_id, tema_id)
                        DO UPDATE SET peso_tema=excluded.peso_tema
                    """, (qid, r["tema_id"], w(r["peso (1..10)"])))
            conn.commit()
            st.success("Temas salvos. Vá para B1.2.")
            st.rerun()

    # ---------- B1.2 ----------
    with tab2:
        # temas selecionados (peso_tema) determinam a lista
        sel_temas = df_from_query(conn, """
            SELECT t.tema_id, t.nome, t.eixo_id, pt.peso_tema
            FROM peso_tema pt
            JOIN tema t ON t.tema_id=pt.tema_id
            WHERE pt.questionario_id=?
            ORDER BY t.eixo_id, t.tema_id
        """, (qid,))

        if sel_temas.empty:
            st.info("Nenhum tema selecionado ainda. Vá na aba B1 e selecione temas.")
        else:
            tema_sel = st.selectbox("Tema selecionado", sel_temas["tema_id"].tolist(), key=f"b12_tema_{qid}")

            topicos = df_from_query(conn, """
                SELECT topico_id, nome
                FROM topico
                WHERE tema_id=?
                ORDER BY topico_id
            """, (tema_sel,))

            p_p = df_from_query(conn, "SELECT topico_id, peso_topico FROM peso_topico WHERE questionario_id=?", (qid,))
            p_map = dict(zip(p_p["topico_id"], p_p["peso_topico"])) if not p_p.empty else {}

            pedit = topicos.copy()
            pedit["incluir"] = pedit["topico_id"].map(lambda x: x in p_map)
            pedit["peso (1..10)"] = pedit["topico_id"].map(lambda x: int(p_map.get(x, 1)))

            pedit2 = st.data_editor(
                pedit,
                hide_index=True,
                use_container_width=True,
                column_config={
                    "incluir": st.column_config.CheckboxColumn("Incluir"),
                    "peso (1..10)": st.column_config.NumberColumn("Peso", min_value=1, max_value=10, step=1),
                },
                key=f"b12_topicos_editor_{qid}_{tema_sel}"
            )

            if st.button("Salvar tópicos do tema"):
                conn.execute("""
                    DELETE FROM peso_topico
                    WHERE questionario_id=?
                      AND topico_id IN (SELECT topico_id FROM topico WHERE tema_id=?)
                """, (qid, tema_sel))

                for _, r in pedit2.iterrows():
                    if bool(r["incluir"]):
                        conn.execute("""
                            INSERT INTO peso_topico (questionario_id, topico_id, peso_topico)
                            VALUES (?, ?, ?)
                            ON CONFLICT(questionario_id, topico_id)
                            DO UPDATE SET peso_topico=excluded.peso_topico
                        """, (qid, r["topico_id"], w(r["peso (1..10)"])))
                conn.commit()
                st.success("Tópicos salvos. Vá para B2.")
                st.rerun()

    # ---------- B2 ----------
    with tab3:
        sel_topicos = df_from_query(conn, """
            SELECT tp.topico_id, tp.nome, tp.tema_id, pt.peso_topico
            FROM peso_topico pt
            JOIN topico tp ON tp.topico_id=pt.topico_id
            WHERE pt.questionario_id=?
            ORDER BY tp.tema_id, tp.topico_id
        """, (qid,))

        if sel_topicos.empty:
            st.info("Nenhum tópico selecionado ainda. Vá na aba B1.2 e selecione tópicos.")
        else:
            topico_sel = st.selectbox("Tópico selecionado", sel_topicos["topico_id"].tolist(), key=f"b2_topico_{qid}")

            ind = df_from_query(conn, """
                SELECT
                  i.indicador_id,
                  i.nome,
                  i.tipo_indicador,
                  i.psr_tipo,
                  COALESCE(ic.ativo, 0) AS ativo,
                  COALESCE(ic.peso_indicador, 1) AS peso_indicador
                FROM indicador i
                LEFT JOIN indicador_config ic
                  ON ic.indicador_id=i.indicador_id AND ic.questionario_id=?
                WHERE i.topico_id=?
                ORDER BY i.indicador_id
            """, (qid, topico_sel))

            if ind.empty:
                st.info("Não há indicadores nesse tópico.")
            else:
                edit = ind.copy()
                edit["peso (1..10)"] = edit["peso_indicador"]
                edit = edit[["ativo","peso (1..10)","indicador_id","nome","tipo_indicador","psr_tipo"]]

                edit2 = st.data_editor(
                    edit,
                    hide_index=True,
                    use_container_width=True,
                    column_config={
                        "ativo": st.column_config.CheckboxColumn("Ativo"),
                        "peso (1..10)": st.column_config.NumberColumn("Peso", min_value=1, max_value=10, step=1),
                    },
                    key=f"b2_inds_editor_{qid}_{topico_sel}"
                )

                if st.button("Salvar indicadores do tópico"):
                    # salva só os desse tópico (upsert); se desmarcar, deixa ativo=0
                    for _, r in edit2.iterrows():
                        ativo = 1 if bool(r["ativo"]) else 0
                        conn.execute("""
                            INSERT INTO indicador_config (questionario_id, indicador_id, ativo, peso_indicador)
                            VALUES (?, ?, ?, ?)
                            ON CONFLICT(questionario_id, indicador_id)
                            DO UPDATE SET ativo=excluded.ativo, peso_indicador=excluded.peso_indicador
                        """, (qid, r["indicador_id"], ativo, w(r["peso (1..10)"])))
                    conn.commit()
                    st.success("Indicadores salvos.")
                    st.rerun()

    st.divider()

    # indicadores ativos (para C/D/E/F)
    active_inds = df_from_query(conn, """
        SELECT i.indicador_id, i.nome, i.tipo_indicador, i.topico_id
        FROM indicador i
        JOIN indicador_config ic ON ic.indicador_id=i.indicador_id
        WHERE ic.questionario_id=? AND ic.ativo=1
        ORDER BY i.indicador_id
    """, (qid,))

    if active_inds.empty:
        st.warning("Nenhum indicador ativo ainda. Use B2 para ativar indicadores.")
        return

    # ---------------- C) Ajuste de pesos (opcional) ----------------
    st.subheader("C) Ajuste de pesos (opcional)")
    st.caption("Você já definiu pesos em B1 (tema) e B1.2 (tópico) e B2 (indicador). Aqui é só para revisar.")

    # ---------------- D) Faixas ----------------
    st.subheader("D) Faixas de referência (nível 1..5) para CALCULADO")
    calc_inds = df_from_query(conn, """
        SELECT i.indicador_id, i.nome
        FROM indicador i
        JOIN indicador_config ic ON ic.indicador_id=i.indicador_id
        WHERE ic.questionario_id=? AND ic.ativo=1 AND i.tipo_indicador='CALCULADO'
        ORDER BY i.indicador_id
    """, (qid,))
    if calc_inds.empty:
        st.info("Nenhum indicador CALCULADO ativo.")
    else:
        ind_sel = st.selectbox("Indicador calculado", calc_inds["indicador_id"].tolist(), key=f"faixa_ind_{qid}")
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
                "nivel": st.column_config.NumberColumn("Nível", disabled=True),
                "tipo_regra": st.column_config.SelectboxColumn("Tipo regra", options=["INTERVALO","EXATO","DIRETO"]),
            },
            key=f"faixa_editor_{qid}_{ind_sel}"
        )

        if st.button("Salvar faixas"):
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
            st.success("Faixas salvas.")
            st.rerun()

    st.divider()

    # ---------------- E) Recomendações ----------------
    st.subheader("E) Recomendações por nível (Tema / Eixo)")
    used_themes = df_from_query(conn, """
        SELECT DISTINCT t.tema_id, t.nome, t.eixo_id
        FROM tema t
        JOIN topico tp ON tp.tema_id=t.tema_id
        JOIN indicador i ON i.topico_id=tp.topico_id
        JOIN indicador_config ic ON ic.indicador_id=i.indicador_id
        WHERE ic.questionario_id=? AND ic.ativo=1
        ORDER BY t.eixo_id, t.tema_id
    """, (qid,))

    if used_themes.empty:
        st.info("Sem temas usados (ative indicadores primeiro).")
    else:
        tema_sel = st.selectbox("Tema", used_themes["tema_id"].tolist(), key=f"rec_tema_{qid}")
        rec_t = df_from_query(conn, """
            SELECT nivel, recomendacao
            FROM recomendacao_tema
            WHERE questionario_id=? AND tema_id=?
            ORDER BY nivel
        """, (qid, tema_sel))
        if rec_t.empty:
            # tenta default (se existir)
            rec_def = df_from_query(conn, """
                SELECT nivel, recomendacao
                FROM recomendacao_tema_default
                WHERE tema_id=?
                ORDER BY nivel
            """, (tema_sel,))
            if rec_def.empty:
                rec_t = pd.DataFrame({"nivel":[1,2,3,4,5], "recomendacao":[""]*5})
            else:
                rec_t = rec_def

        rec_t_edit = st.data_editor(rec_t, use_container_width=True, hide_index=True,
                                    column_config={"nivel": st.column_config.NumberColumn("Nível", disabled=True)},
                                    key=f"rec_tema_editor_{qid}_{tema_sel}")
        if st.button("Salvar recomendações do Tema"):
            conn.execute("DELETE FROM recomendacao_tema WHERE questionario_id=? AND tema_id=?", (qid, tema_sel))
            for _, r in rec_t_edit.iterrows():
                if str(r["recomendacao"]).strip():
                    conn.execute("""
                        INSERT INTO recomendacao_tema (questionario_id, tema_id, nivel, recomendacao)
                        VALUES (?, ?, ?, ?)
                    """, (qid, tema_sel, int(r["nivel"]), str(r["recomendacao"]).strip()))
            conn.commit()
            st.success("Recomendações do tema salvas.")
            st.rerun()

        used_eixos = df_from_query(conn, """
            SELECT DISTINCT t.eixo_id
            FROM tema t
            JOIN topico tp ON tp.tema_id=t.tema_id
            JOIN indicador i ON i.topico_id=tp.topico_id
            JOIN indicador_config ic ON ic.indicador_id=i.indicador_id
            WHERE ic.questionario_id=? AND ic.ativo=1
            ORDER BY t.eixo_id
        """, (qid,))
        eixo_sel = st.selectbox("Eixo", used_eixos["eixo_id"].tolist(), key=f"rec_eixo_{qid}")

        rec_e = df_from_query(conn, """
            SELECT nivel, recomendacao
            FROM recomendacao_eixo
            WHERE questionario_id=? AND eixo_id=?
            ORDER BY nivel
        """, (qid, eixo_sel))
        if rec_e.empty:
            rec_def = df_from_query(conn, """
                SELECT nivel, recomendacao
                FROM recomendacao_eixo_default
                WHERE eixo_id=?
                ORDER BY nivel
            """, (eixo_sel,))
            if rec_def.empty:
                rec_e = pd.DataFrame({"nivel":[1,2,3,4,5], "recomendacao":[""]*5})
            else:
                rec_e = rec_def

        rec_e_edit = st.data_editor(rec_e, use_container_width=True, hide_index=True,
                                    column_config={"nivel": st.column_config.NumberColumn("Nível", disabled=True)},
                                    key=f"rec_eixo_editor_{qid}_{eixo_sel}")
        if st.button("Salvar recomendações do Eixo"):
            conn.execute("DELETE FROM recomendacao_eixo WHERE questionario_id=? AND eixo_id=?", (qid, eixo_sel))
            for _, r in rec_e_edit.iterrows():
                if str(r["recomendacao"]).strip():
                    conn.execute("""
                        INSERT INTO recomendacao_eixo (questionario_id, eixo_id, nivel, recomendacao)
                        VALUES (?, ?, ?, ?)
                    """, (qid, eixo_sel, int(r["nivel"]), str(r["recomendacao"]).strip()))
            conn.commit()
            st.success("Recomendações do eixo salvas.")
            st.rerun()

    st.divider()

    # ---------------- F) Export ----------------
    st.subheader("F) Exportar SETUP_QUESTIONARIO.xlsx")
    if st.button("Gerar arquivo SETUP_QUESTIONARIO.xlsx"):
        xlsx_bytes = export_setup_xlsx(conn, qid)
        st.download_button(
            "Baixar SETUP_QUESTIONARIO.xlsx",
            data=xlsx_bytes,
            file_name=f"SETUP_QUESTIONARIO_{qid}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
