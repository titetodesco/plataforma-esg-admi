import streamlit as st
import pandas as pd
from utils.setup_export import export_setup_xlsx


# -------------------- Helpers --------------------
def df_from_query(conn, sql: str, params=()):
    cur = conn.execute(sql, params)
    rows = cur.fetchall()
    cols = [d[0] for d in cur.description] if cur.description else []
    return pd.DataFrame(rows, columns=cols)


def df_from_query_cached(conn, sql: str, params=()):
    ver = _cache_ver()
    cache_ver = st.session_state.get("_sql_cache_ver")
    if cache_ver != ver:
        st.session_state["_sql_cache_ver"] = ver
        st.session_state["_sql_cache_store"] = {}

    store = st.session_state.setdefault("_sql_cache_store", {})
    key = (sql, tuple(params) if params is not None else ())
    if key in store:
        return store[key]

    df = df_from_query(conn, sql, params)
    store[key] = df
    return df


def w_1a10(x):
    try:
        v = int(float(str(x).replace(",", ".")))
    except Exception:
        v = 1
    return max(1, min(10, v))


def _cache_get(key: str):
    return st.session_state.get(key)


def _cache_set(key: str, value):
    st.session_state[key] = value


def _cache_ver():
    return int(st.session_state.get("_cache_ver", 0))


def _cache_bump():
    st.session_state["_cache_ver"] = _cache_ver() + 1


def load_macro_cache(conn):
    """
    Carrega EIXO/TEMA/TOPICO/INDICADOR uma vez por sessão (e recarrega quando _cache_ver muda).
    Isso reduz MUITO a lentidão no Streamlit Cloud.
    """
    ver = _cache_ver()
    cached = _cache_get(f"_macro_cache_{ver}")
    if cached is not None:
        return cached

    eixos = df_from_query(conn, "SELECT eixo_id, codigo, nome FROM eixo ORDER BY eixo_id")
    temas = df_from_query(conn, "SELECT tema_id, eixo_id, nome FROM tema ORDER BY eixo_id, tema_id")
    topicos = df_from_query(conn, "SELECT topico_id, tema_id, nome FROM topico ORDER BY tema_id, topico_id")
    indicadores = df_from_query(
        conn,
        """
        SELECT i.indicador_id, i.topico_id, i.nome, i.tipo_indicador, i.psr_tipo
        FROM indicador i
        ORDER BY i.indicador_id
        """,
    )

    cached = {
        "eixos": eixos,
        "temas": temas,
        "topicos": topicos,
        "indicadores": indicadores,
    }
    _cache_set(f"_macro_cache_{ver}", cached)
    return cached


def load_questionario_cache(conn, questionario_id: str):
    """
    Cache de configurações do questionário para evitar bater no Turso a cada clique.
    Recarrega quando _cache_ver muda.
    """
    ver = _cache_ver()
    key = f"_qcache_{questionario_id}_{ver}"
    cached = _cache_get(key)
    if cached is not None:
        return cached

    qmeta = df_from_query(
        conn,
        """
        SELECT questionario_id, setor, porte, regiao, versao, status, observacao
        FROM questionario
        WHERE questionario_id=?
        """,
        (questionario_id,),
    )

    peso_tema = df_from_query(conn, "SELECT tema_id, peso_tema FROM peso_tema WHERE questionario_id=?", (questionario_id,))
    peso_topico = df_from_query(conn, "SELECT topico_id, peso_topico FROM peso_topico WHERE questionario_id=?", (questionario_id,))
    ind_cfg = df_from_query(
        conn,
        """
        SELECT indicador_id, ativo, peso_indicador
        FROM indicador_config
        WHERE questionario_id=?
        """,
        (questionario_id,),
    )

    cached = {
        "qmeta": qmeta,
        "peso_tema": peso_tema,
        "peso_topico": peso_topico,
        "ind_cfg": ind_cfg,
    }
    _cache_set(key, cached)
    return cached


def sync_recomendacoes_default_para_questionario(conn, questionario_id: str, used_themes: pd.DataFrame) -> bool:
    if used_themes.empty:
        return False

    changed = False
    tema_ids = used_themes["tema_id"].dropna().astype(str).unique().tolist()
    eixo_ids = used_themes["eixo_id"].dropna().astype(str).unique().tolist()

    for tema_id in tema_ids:
        cur_def = conn.execute(
            "SELECT COUNT(*) FROM recomendacao_tema_default WHERE tema_id=?",
            (tema_id,),
        )
        qtd_def = int(cur_def.fetchall()[0][0]) if cur_def else 0

        cur_q = conn.execute(
            "SELECT COUNT(*) FROM recomendacao_tema WHERE questionario_id=? AND tema_id=?",
            (questionario_id, tema_id),
        )
        qtd_q = int(cur_q.fetchall()[0][0]) if cur_q else 0

        if qtd_def > 0 and qtd_q < qtd_def:
            conn.execute(
                """
                INSERT INTO recomendacao_tema (questionario_id, tema_id, nivel, recomendacao)
                SELECT ?, ?, d.nivel, d.recomendacao
                FROM recomendacao_tema_default d
                WHERE d.tema_id=?
                  AND NOT EXISTS (
                    SELECT 1
                    FROM recomendacao_tema rt
                    WHERE rt.questionario_id=?
                      AND rt.tema_id=?
                      AND rt.nivel=d.nivel
                  )
                """,
                (questionario_id, tema_id, tema_id, questionario_id, tema_id),
            )
            changed = True

    for eixo_id in eixo_ids:
        cur_def = conn.execute(
            "SELECT COUNT(*) FROM recomendacao_eixo_default WHERE eixo_id=?",
            (eixo_id,),
        )
        qtd_def = int(cur_def.fetchall()[0][0]) if cur_def else 0

        cur_q = conn.execute(
            "SELECT COUNT(*) FROM recomendacao_eixo WHERE questionario_id=? AND eixo_id=?",
            (questionario_id, eixo_id),
        )
        qtd_q = int(cur_q.fetchall()[0][0]) if cur_q else 0

        if qtd_def > 0 and qtd_q < qtd_def:
            conn.execute(
                """
                INSERT INTO recomendacao_eixo (questionario_id, eixo_id, nivel, recomendacao)
                SELECT ?, ?, d.nivel, d.recomendacao
                FROM recomendacao_eixo_default d
                WHERE d.eixo_id=?
                  AND NOT EXISTS (
                    SELECT 1
                    FROM recomendacao_eixo re
                    WHERE re.questionario_id=?
                      AND re.eixo_id=?
                      AND re.nivel=d.nivel
                  )
                """,
                (questionario_id, eixo_id, eixo_id, questionario_id, eixo_id),
            )
            changed = True

    if changed:
        conn.commit()
        _cache_bump()
    return changed


# -------------------- UI --------------------
def render_setup_builder(conn):
    st.header("Setup do Questionário (Builder)")

    macro = load_macro_cache(conn)

    # ---------- A) Selecionar / Criar questionário ----------
    st.subheader("A) Selecionar ou criar questionário (perfil)")

    qdf = df_from_query(
        conn,
        """
        SELECT questionario_id, setor, porte, regiao, versao, status
        FROM questionario
        ORDER BY created_at DESC
        """,
    )

    default_sel = st.session_state.get("_selected_qid", "(novo)")
    options = ["(novo)"] + (qdf["questionario_id"].tolist() if not qdf.empty else [])
    if default_sel not in options:
        default_sel = "(novo)"

    selected = st.selectbox("Questionário", options, index=options.index(default_sel), key="_qid_select")

    if selected == "(novo)":
        with st.expander("Criar novo questionário", expanded=True):
            qid = st.text_input("QUESTIONARIO_ID (ex.: QST_DEFAULT)")
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

                exists = df_from_query(conn, "SELECT 1 FROM questionario WHERE questionario_id=? LIMIT 1", (qid.strip(),))
                if not exists.empty:
                    st.warning("Esse QUESTIONARIO_ID já existe. Selecione-o no dropdown.")
                    st.stop()

                conn.execute(
                    """
                    INSERT INTO questionario (questionario_id, setor, porte, regiao, versao, status, observacao)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (qid.strip(), setor.strip(), porte.strip(), regiao.strip(), versao.strip(), status, obs.strip()),
                )
                conn.commit()
                _cache_bump()
                st.session_state["_selected_qid"] = qid.strip()
                st.success("Questionário criado. Selecione-o no dropdown acima.")
        return

    # Fix selection in session
    st.session_state["_selected_qid"] = selected
    qid = selected

    qcache = load_questionario_cache(conn, qid)
    qmeta = qcache["qmeta"]
    if qmeta.empty:
        st.error("Questionário não encontrado no banco.")
        return

    st.caption(
        f"Perfil: setor={qmeta.loc[0,'setor']} | porte={qmeta.loc[0,'porte']} | "
        f"regiao={qmeta.loc[0,'regiao']} | versao={qmeta.loc[0,'versao']} | status={qmeta.loc[0,'status']}"
    )

    st.divider()

    # ---------- B) Seleção ----------
    st.subheader("B) Seleção — Temas → Tópicos → Indicadores (B2 por Tema)")

    tab1, tab2, tab3 = st.tabs(["B1) Temas (todos)", "B1.2) Tópicos", "B2) Indicadores (por Tema)"])

    # --- B1: Temas (lista completa) ---
    with tab1:
        temas = macro["temas"][["tema_id", "eixo_id", "nome"]].sort_values(by=["eixo_id", "tema_id"]).reset_index(drop=True)
        if temas.empty:
            st.warning("Nenhum tema encontrado na macro-base. Publique a macro-base e tente novamente.")
            return

        # map do peso_tema existente
        peso_tema = qcache["peso_tema"]
        tema_map = dict(zip(peso_tema["tema_id"], peso_tema["peso_tema"])) if not peso_tema.empty else {}

        temas["incluir"] = temas["tema_id"].map(lambda x: x in tema_map)
        temas["peso (1..10)"] = temas["tema_id"].map(lambda x: int(tema_map.get(x, 1)))

        # Mostra eixo junto
        temas = temas[["eixo_id", "tema_id", "nome", "incluir", "peso (1..10)"]]

        with st.form(key=f"form_b1_temas_{qid}"):
            temas_edit = st.data_editor(
                temas,
                hide_index=True,
                use_container_width=True,
                column_config={
                    "incluir": st.column_config.CheckboxColumn("Incluir"),
                    "peso (1..10)": st.column_config.NumberColumn("Peso", min_value=1, max_value=10, step=1),
                },
                key=f"b1_temas_{qid}",
            )

            submit_temas = st.form_submit_button("Salvar Temas selecionados")

        if submit_temas:
            # remove todos e reinsere marcados (mais simples)
            conn.execute("DELETE FROM peso_tema WHERE questionario_id=?", (qid,))
            for _, r in temas_edit.iterrows():
                if bool(r["incluir"]):
                    conn.execute(
                        """
                        INSERT INTO peso_tema (questionario_id, tema_id, peso_tema)
                        VALUES (?, ?, ?)
                        """,
                        (qid, r["tema_id"], w_1a10(r["peso (1..10)"])),
                    )
            conn.commit()
            _cache_bump()
            st.success("Temas salvos. Vá para B1.2 (Tópicos).")

    # --- B1.2: Tópicos (dos temas selecionados) ---
    with tab2:
        # temas selecionados
        sel_temas = qcache["peso_tema"][["tema_id"]].copy() if not qcache["peso_tema"].empty else pd.DataFrame(columns=["tema_id"])
        if not sel_temas.empty:
            sel_temas = sel_temas.sort_values(by=["tema_id"]).reset_index(drop=True)

        if sel_temas.empty:
            st.info("Nenhum tema selecionado ainda. Vá na aba B1 e selecione temas.")
        else:
            tema_ids = sel_temas["tema_id"].tolist()
            topicos = macro["topicos"][macro["topicos"]["tema_id"].isin(tema_ids)].copy()

            peso_topico = qcache["peso_topico"]
            topico_map = dict(zip(peso_topico["topico_id"], peso_topico["peso_topico"])) if not peso_topico.empty else {}

            topicos["incluir"] = topicos["topico_id"].map(lambda x: x in topico_map)
            topicos["peso (1..10)"] = topicos["topico_id"].map(lambda x: int(topico_map.get(x, 1)))

            topicos = topicos[["tema_id", "topico_id", "nome", "incluir", "peso (1..10)"]]

            with st.form(key=f"form_b12_topicos_{qid}"):
                topicos_edit = st.data_editor(
                    topicos,
                    hide_index=True,
                    use_container_width=True,
                    column_config={
                        "incluir": st.column_config.CheckboxColumn("Incluir"),
                        "peso (1..10)": st.column_config.NumberColumn("Peso", min_value=1, max_value=10, step=1),
                    },
                    key=f"b12_topicos_{qid}",
                )

                submit_topicos = st.form_submit_button("Salvar Tópicos selecionados")

            if submit_topicos:
                conn.execute("DELETE FROM peso_topico WHERE questionario_id=?", (qid,))
                for _, r in topicos_edit.iterrows():
                    if bool(r["incluir"]):
                        conn.execute(
                            """
                            INSERT INTO peso_topico (questionario_id, topico_id, peso_topico)
                            VALUES (?, ?, ?)
                            """,
                            (qid, r["topico_id"], w_1a10(r["peso (1..10)"])),
                        )
                conn.commit()
                _cache_bump()
                st.success("Tópicos salvos. Vá para B2 (Indicadores).")

    # --- B2: Indicadores por Tema (sem filtro por eixo; lista por tema selecionado) ---
    with tab3:
        if qcache["peso_tema"].empty:
            sel_temas = pd.DataFrame(columns=["tema_id", "nome", "eixo_id"])
        else:
            sel_temas = (
                macro["temas"][macro["temas"]["tema_id"].isin(qcache["peso_tema"]["tema_id"])][["tema_id", "nome", "eixo_id"]]
                .sort_values(by=["eixo_id", "tema_id"])
                .reset_index(drop=True)
            )

        if sel_temas.empty:
            st.info("Nenhum tema selecionado ainda. Vá na aba B1 e selecione temas.")
        else:
            tema_choice = st.selectbox(
                "Tema selecionado",
                sel_temas["tema_id"].tolist(),
                key=f"b2_tema_sel_{qid}",
            )

            # tópicos selecionados do tema
            if qcache["peso_topico"].empty:
                sel_topicos = pd.DataFrame(columns=["topico_id", "nome"])
            else:
                sel_topicos = (
                    macro["topicos"][
                        (macro["topicos"]["tema_id"] == tema_choice)
                        & (macro["topicos"]["topico_id"].isin(qcache["peso_topico"]["topico_id"]))
                    ][["topico_id", "nome"]]
                    .sort_values(by=["topico_id"])
                    .reset_index(drop=True)
                )

            if sel_topicos.empty:
                st.info("Nenhum tópico selecionado para este tema. Vá na aba B1.2 e selecione tópicos.")
            else:
                topico_ids = sel_topicos["topico_id"].tolist()

                # indicadores do tema (via tópicos selecionados)
                ind_base = (
                    macro["indicadores"][macro["indicadores"]["topico_id"].isin(topico_ids)][
                        ["indicador_id", "nome", "tipo_indicador", "psr_tipo", "topico_id"]
                    ]
                    .sort_values(by=["indicador_id"])
                    .reset_index(drop=True)
                )

                # join com indicador_config
                ind_cfg = qcache["ind_cfg"]
                cfg_map = {}
                if not ind_cfg.empty:
                    for _, r in ind_cfg.iterrows():
                        cfg_map[r["indicador_id"]] = (int(r["ativo"]), int(r["peso_indicador"]))

                ind_base["ativo"] = ind_base["indicador_id"].map(lambda x: cfg_map.get(x, (0, 1))[0])
                ind_base["peso (1..10)"] = ind_base["indicador_id"].map(lambda x: cfg_map.get(x, (0, 1))[1])

                # adiciona nome do tópico para facilitar navegação
                tp_name_map = dict(zip(sel_topicos["topico_id"], sel_topicos["nome"]))
                ind_base["topico_nome"] = ind_base["topico_id"].map(lambda x: tp_name_map.get(x, ""))

                ind_edit = ind_base[["ativo", "peso (1..10)", "indicador_id", "nome", "topico_id", "topico_nome", "tipo_indicador", "psr_tipo"]].copy()

                ind_edit2 = st.data_editor(
                    ind_edit,
                    hide_index=True,
                    use_container_width=True,
                    column_config={
                        "ativo": st.column_config.CheckboxColumn("Ativo"),
                        "peso (1..10)": st.column_config.NumberColumn("Peso", min_value=1, max_value=10, step=1),
                    },
                    key=f"b2_inds_{qid}_{tema_choice}",
                )

                colA, colB, colC = st.columns([1, 1, 2])

                with colA:
                    if st.button("Ativar todos do tema"):
                        for _, r in ind_edit2.iterrows():
                            conn.execute(
                                """
                                INSERT INTO indicador_config (questionario_id, indicador_id, ativo, peso_indicador)
                                VALUES (?, ?, 1, 1)
                                ON CONFLICT(questionario_id, indicador_id)
                                DO UPDATE SET ativo=1, peso_indicador=excluded.peso_indicador
                                """,
                                (qid, r["indicador_id"]),
                            )
                        conn.commit()
                        _cache_bump()
                        st.success("Todos os indicadores do tema foram ativados (peso=1).")

                with colB:
                    if st.button("Desativar todos do tema"):
                        for _, r in ind_edit2.iterrows():
                            conn.execute(
                                """
                                INSERT INTO indicador_config (questionario_id, indicador_id, ativo, peso_indicador)
                                VALUES (?, ?, 0, 1)
                                ON CONFLICT(questionario_id, indicador_id)
                                DO UPDATE SET ativo=0
                                """,
                                (qid, r["indicador_id"]),
                            )
                        conn.commit()
                        _cache_bump()
                        st.success("Todos os indicadores do tema foram desativados.")

                with colC:
                    if st.button("Salvar Indicadores do tema"):
                        for _, r in ind_edit2.iterrows():
                            ativo = 1 if bool(r["ativo"]) else 0
                            conn.execute(
                                """
                                INSERT INTO indicador_config (questionario_id, indicador_id, ativo, peso_indicador)
                                VALUES (?, ?, ?, ?)
                                ON CONFLICT(questionario_id, indicador_id)
                                DO UPDATE SET ativo=excluded.ativo, peso_indicador=excluded.peso_indicador
                                """,
                                (qid, r["indicador_id"], ativo, w_1a10(r["peso (1..10)"])),
                            )
                        conn.commit()
                        _cache_bump()
                        st.success("Indicadores salvos.")

    st.divider()

    # ---------- D/E/F mantidas (mais leve: só roda quando há indicadores ativos) ----------
    ind_cfg = qcache["ind_cfg"]
    active_ids = ind_cfg[ind_cfg["ativo"] == 1]["indicador_id"].tolist() if not ind_cfg.empty else []
    if active_ids:
        ind_active = macro["indicadores"][macro["indicadores"]["indicador_id"].isin(active_ids)][["indicador_id", "topico_id", "tipo_indicador"]]
        active_axes = (
            ind_active
            .merge(macro["topicos"][["topico_id", "tema_id"]], on="topico_id", how="left")
            .merge(macro["temas"][["tema_id", "eixo_id", "nome"]], on="tema_id", how="left")
            .groupby("eixo_id", dropna=False)
            .size()
            .reset_index(name="qtd")
            .sort_values(by=["eixo_id"])
            .reset_index(drop=True)
        )
    else:
        active_axes = pd.DataFrame(columns=["eixo_id", "qtd"])

    if active_axes.empty:
        st.warning("Nenhum indicador ativo ainda. Ative indicadores na etapa B2.")
        return

    st.subheader("D) Faixas (indicadores CALCULADO)")
    calc_inds = (
        macro["indicadores"][
            (macro["indicadores"]["indicador_id"].isin(active_ids))
            & (macro["indicadores"]["tipo_indicador"] == "CALCULADO")
        ][["indicador_id", "nome"]]
        .sort_values(by=["indicador_id"])
        .reset_index(drop=True)
    )
    if calc_inds.empty:
        st.info("Nenhum indicador CALCULADO ativo.")
    else:
        faixa_status = df_from_query_cached(
            conn,
            """
            SELECT indicador_id, COUNT(*) AS qtd_niveis
            FROM faixa_referencia
            WHERE questionario_id=?
            GROUP BY indicador_id
            """,
            (qid,),
        )
        faixa_map = dict(zip(faixa_status["indicador_id"], faixa_status["qtd_niveis"])) if not faixa_status.empty else {}
        missing_faixas = [ind for ind in calc_inds["indicador_id"].tolist() if int(faixa_map.get(ind, 0)) < 5]
        if missing_faixas:
            st.warning(
                "Indicadores calculados sem faixas completas (5 níveis): "
                + ", ".join(missing_faixas)
                + ". Complete na etapa D antes de exportar."
            )

        ind_sel = st.selectbox("Indicador calculado", calc_inds["indicador_id"].tolist(), key=f"faixa_ind_{qid}")

        faixa = df_from_query_cached(
            conn,
            """
            SELECT nivel, tipo_regra, valor_min, valor_max, valor_exato, rotulo
            FROM faixa_referencia
            WHERE questionario_id=? AND indicador_id=?
            ORDER BY nivel
            """,
            (qid, ind_sel),
        )

        if faixa.empty:
            faixa = pd.DataFrame(
                {"nivel": [1, 2, 3, 4, 5],
                 "tipo_regra": ["INTERVALO"] * 5,
                 "valor_min": [None] * 5,
                 "valor_max": [None] * 5,
                 "valor_exato": [None] * 5,
                 "rotulo": [""] * 5}
            )

        faixa_edit = st.data_editor(
            faixa,
            use_container_width=True,
            hide_index=True,
            column_config={
                "nivel": st.column_config.NumberColumn("Nível", disabled=True),
                "tipo_regra": st.column_config.SelectboxColumn("Tipo regra", options=["INTERVALO", "EXATO", "DIRETO"]),
            },
            key=f"faixa_editor_{qid}_{ind_sel}",
        )

        if st.button("Salvar faixas"):
            conn.execute("DELETE FROM faixa_referencia WHERE questionario_id=? AND indicador_id=?", (qid, ind_sel))
            for _, r in faixa_edit.iterrows():
                conn.execute(
                    """
                    INSERT INTO faixa_referencia
                    (questionario_id, indicador_id, nivel, tipo_regra, valor_min, valor_max, valor_exato, rotulo)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        qid,
                        ind_sel,
                        int(r["nivel"]),
                        str(r["tipo_regra"]).strip(),
                        r["valor_min"],
                        r["valor_max"],
                        r["valor_exato"],
                        str(r.get("rotulo", "") or ""),
                    ),
                )
            conn.commit()
            _cache_bump()
            st.success("Faixas salvas.")

    st.divider()

    st.subheader("E) Recomendações por nível (Tema / Eixo)")
    if active_ids:
        used_themes = (
            macro["indicadores"][macro["indicadores"]["indicador_id"].isin(active_ids)][["indicador_id", "topico_id"]]
            .merge(macro["topicos"][["topico_id", "tema_id"]], on="topico_id", how="left")
            .merge(macro["temas"][["tema_id", "nome", "eixo_id"]], on="tema_id", how="left")
            [["tema_id", "nome", "eixo_id"]]
            .drop_duplicates()
            .sort_values(by=["eixo_id", "tema_id"])
            .reset_index(drop=True)
        )
    else:
        used_themes = pd.DataFrame(columns=["tema_id", "nome", "eixo_id"])

    if used_themes.empty:
        st.info("Sem temas usados (ative indicadores primeiro).")
    else:
        sync_recomendacoes_default_para_questionario(conn, qid, used_themes)

        tema_sel = st.selectbox("Tema", used_themes["tema_id"].tolist(), key=f"rec_tema_{qid}")

        rec_t = df_from_query_cached(
            conn,
            """
            SELECT nivel, recomendacao
            FROM recomendacao_tema
            WHERE questionario_id=? AND tema_id=?
            ORDER BY nivel
            """,
            (qid, tema_sel),
        )
        if rec_t.empty:
            rec_def = df_from_query_cached(
                conn,
                """
                SELECT nivel, recomendacao
                FROM recomendacao_tema_default
                WHERE tema_id=?
                ORDER BY nivel
                """,
                (tema_sel,),
            )
            rec_t = rec_def if not rec_def.empty else pd.DataFrame({"nivel": [1,2,3,4,5], "recomendacao": [""]*5})

        rec_t_edit = st.data_editor(
            rec_t,
            use_container_width=True,
            hide_index=True,
            column_config={"nivel": st.column_config.NumberColumn("Nível", disabled=True)},
            key=f"rec_tema_editor_{qid}_{tema_sel}",
        )
        if st.button("Salvar recomendações do Tema"):
            conn.execute("DELETE FROM recomendacao_tema WHERE questionario_id=? AND tema_id=?", (qid, tema_sel))
            for _, r in rec_t_edit.iterrows():
                if str(r["recomendacao"]).strip():
                    conn.execute(
                        """
                        INSERT INTO recomendacao_tema (questionario_id, tema_id, nivel, recomendacao)
                        VALUES (?, ?, ?, ?)
                        """,
                        (qid, tema_sel, int(r["nivel"]), str(r["recomendacao"]).strip()),
                    )
            conn.commit()
            _cache_bump()
            st.success("Recomendações do tema salvas.")

        used_eixos = used_themes[["eixo_id"]].drop_duplicates().sort_values(by=["eixo_id"]).reset_index(drop=True)
        eixo_sel = st.selectbox("Eixo", used_eixos["eixo_id"].tolist(), key=f"rec_eixo_{qid}")

        rec_e = df_from_query_cached(
            conn,
            """
            SELECT nivel, recomendacao
            FROM recomendacao_eixo
            WHERE questionario_id=? AND eixo_id=?
            ORDER BY nivel
            """,
            (qid, eixo_sel),
        )
        if rec_e.empty:
            rec_def = df_from_query_cached(
                conn,
                """
                SELECT nivel, recomendacao
                FROM recomendacao_eixo_default
                WHERE eixo_id=?
                ORDER BY nivel
                """,
                (eixo_sel,),
            )
            rec_e = rec_def if not rec_def.empty else pd.DataFrame({"nivel": [1,2,3,4,5], "recomendacao": [""]*5})

        rec_e_edit = st.data_editor(
            rec_e,
            use_container_width=True,
            hide_index=True,
            column_config={"nivel": st.column_config.NumberColumn("Nível", disabled=True)},
            key=f"rec_eixo_editor_{qid}_{eixo_sel}",
        )
        if st.button("Salvar recomendações do Eixo"):
            conn.execute("DELETE FROM recomendacao_eixo WHERE questionario_id=? AND eixo_id=?", (qid, eixo_sel))
            for _, r in rec_e_edit.iterrows():
                if str(r["recomendacao"]).strip():
                    conn.execute(
                        """
                        INSERT INTO recomendacao_eixo (questionario_id, eixo_id, nivel, recomendacao)
                        VALUES (?, ?, ?, ?)
                        """,
                        (qid, eixo_sel, int(r["nivel"]), str(r["recomendacao"]).strip()),
                    )
            conn.commit()
            _cache_bump()
            st.success("Recomendações do eixo salvas.")

    st.divider()

    st.subheader("F) Exportar SETUP_QUESTIONARIO.xlsx")
    if st.button("Gerar arquivo SETUP_QUESTIONARIO.xlsx"):
        xlsx_bytes = export_setup_xlsx(conn, qid)
        st.download_button(
            "Baixar SETUP_QUESTIONARIO.xlsx",
            data=xlsx_bytes,
            file_name=f"SETUP_QUESTIONARIO_{qid}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
