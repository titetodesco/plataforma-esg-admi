import streamlit as st
import pandas as pd
from utils.excel_io import load_macrobase, export_macrobase_xlsx


def _bump_cache_ver():
    st.session_state["_cache_ver"] = int(st.session_state.get("_cache_ver", 0)) + 1


def _w_1a10(x):
    try:
        v = int(float(str(x).replace(",", ".")))
    except Exception:
        v = 1
    return max(1, min(10, v))


def _safe_rollback(conn):
    try:
        conn.rollback()
    except Exception:
        pass


def _friendly_db_error(e):
    msg = str(e)
    if "'result'" in msg:
        return "Falha retornada pelo Turso/libsql-client (detalhe de resposta inválida). Verifique dados duplicados/chaves e tente novamente."
    return msg


def _set_crud_sec_next(secao: str):
    st.session_state["crud_macrobase_sec_next"] = secao


def _get_existing_ids(conn, table: str, id_col: str):
    rows = conn.execute(f"SELECT {id_col} FROM {table}").fetchall()
    return {str(r[0]).strip() for r in rows if r and r[0] is not None}


def _collect_dependency_messages(conn, checks):
    msgs = []
    for label, sql, params, col_idx in checks:
        rows = conn.execute(sql, params).fetchall()
        if not rows:
            continue
        vals = []
        for r in rows[:5]:
            try:
                vals.append(str(r[col_idx]).strip())
            except Exception:
                pass
        preview = ", ".join([v for v in vals if v])
        if len(rows) > 5 and preview:
            preview += ", ..."
        if preview:
            msgs.append(f"- {label}: {len(rows)} registro(s) (ex.: {preview})")
        else:
            msgs.append(f"- {label}: {len(rows)} registro(s)")
    return msgs


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
            num_rows="dynamic",
            column_config={
                "eixo_id": st.column_config.TextColumn("eixo_id"),
                "peso_default": st.column_config.NumberColumn("peso_default", min_value=1, max_value=10, step=1),
            },
            key="crud_eixo_editor",
        )
        save_eixos = st.form_submit_button("Salvar alterações de Eixos")

    if save_eixos:
        try:
            existing_ids = _get_existing_ids(conn, "eixo", "eixo_id")
            for _, r in eixos_edit.iterrows():
                eixo_id = str(r.get("eixo_id", "") or "").strip()
                if not eixo_id:
                    continue
                codigo = str(r.get("codigo", "") or "").strip() or eixo_id
                nome = str(r.get("nome", "") or "").strip()
                descricao = str(r.get("descricao", "") or "").strip()
                peso = _w_1a10(r.get("peso_default", 1))
                if not nome:
                    raise ValueError(f"nome obrigatório para eixo_id '{eixo_id}'.")

                if eixo_id in existing_ids:
                    conn.execute(
                        """
                        UPDATE eixo
                        SET codigo=?, nome=?, descricao=?, peso_default=?
                        WHERE eixo_id=?
                        """,
                        (codigo, nome, descricao, peso, eixo_id),
                    )
                else:
                    conn.execute(
                        """
                        INSERT INTO eixo (eixo_id, codigo, nome, descricao, peso_default)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (eixo_id, codigo, nome, descricao, peso),
                    )
                    existing_ids.add(eixo_id)
            conn.commit()
            _bump_cache_ver()
            _set_crud_sec_next("Eixos")
            st.success("Eixos atualizados.")
            st.rerun()
        except Exception as e:
            _safe_rollback(conn)
            st.error(f"Erro ao salvar eixos: {_friendly_db_error(e)}")

    if not eixos.empty:
        eixo_del = st.selectbox("Excluir eixo_id", eixos["eixo_id"].tolist(), key="del_eixo_id")
        if st.button("Excluir Eixo"):
            deps = _collect_dependency_messages(
                conn,
                [
                    (
                        "Temas vinculados",
                        "SELECT tema_id FROM tema WHERE eixo_id=? ORDER BY tema_id",
                        (eixo_del,),
                        0,
                    )
                ],
            )
            if deps:
                st.error(f"Não é possível excluir o eixo '{eixo_del}' porque há dependências:")
                st.markdown("\n".join(deps))
                return
            try:
                conn.execute("DELETE FROM eixo WHERE eixo_id=?", (eixo_del,))
                conn.commit()
                _bump_cache_ver()
                _set_crud_sec_next("Eixos")
                st.success(f"Eixo {eixo_del} excluído.")
                st.rerun()
            except Exception as e:
                _safe_rollback(conn)
                st.error(f"Erro ao excluir eixo: {_friendly_db_error(e)}")


def _render_crud_tema(conn):
    st.markdown("### CRUD Tema (MVP)")

    eixos = load_table_df(conn, "eixo")
    eixo_opts = eixos["eixo_id"].tolist() if not eixos.empty else []
    eixo_set = set(eixo_opts)

    temas = load_table_df(conn, "tema")
    if temas.empty:
        temas = pd.DataFrame(columns=["tema_id", "eixo_id", "codigo", "nome", "descricao", "peso_default"])

    temas = temas[["tema_id", "eixo_id", "codigo", "nome", "descricao", "peso_default"]].copy()

    with st.form("crud_tema_form"):
        temas_edit = st.data_editor(
            temas,
            hide_index=True,
            use_container_width=True,
            num_rows="dynamic",
            column_config={
                "tema_id": st.column_config.TextColumn("tema_id"),
                "eixo_id": st.column_config.SelectboxColumn("eixo_id", options=eixo_opts),
                "peso_default": st.column_config.NumberColumn("peso_default", min_value=1, max_value=10, step=1),
            },
            key="crud_tema_editor",
        )
        save_temas = st.form_submit_button("Salvar alterações de Temas")

    if save_temas:
        try:
            existing_ids = _get_existing_ids(conn, "tema", "tema_id")
            for _, r in temas_edit.iterrows():
                tema_id = str(r.get("tema_id", "") or "").strip()
                if not tema_id:
                    continue
                eixo_id = str(r.get("eixo_id", "") or "").strip()
                if eixo_id not in eixo_set:
                    raise ValueError(f"eixo_id inválido em Temas: '{eixo_id}'. Selecione um eixo existente.")
                codigo = str(r.get("codigo", "") or "").strip() or tema_id
                nome = str(r.get("nome", "") or "").strip()
                descricao = str(r.get("descricao", "") or "").strip()
                peso = _w_1a10(r.get("peso_default", 1))
                if not nome:
                    raise ValueError(f"nome obrigatório para tema_id '{tema_id}'.")

                if tema_id in existing_ids:
                    conn.execute(
                        """
                        UPDATE tema
                        SET eixo_id=?, codigo=?, nome=?, descricao=?, peso_default=?
                        WHERE tema_id=?
                        """,
                        (eixo_id, codigo, nome, descricao, peso, tema_id),
                    )
                else:
                    conn.execute(
                        """
                        INSERT INTO tema (tema_id, eixo_id, codigo, nome, descricao, peso_default)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (tema_id, eixo_id, codigo, nome, descricao, peso),
                    )
                    existing_ids.add(tema_id)
            conn.commit()
            _bump_cache_ver()
            _set_crud_sec_next("Temas")
            st.success("Temas atualizados.")
            st.rerun()
        except Exception as e:
            _safe_rollback(conn)
            st.error(f"Erro ao salvar temas: {_friendly_db_error(e)}")

    if not temas.empty:
        tema_del = st.selectbox("Excluir tema_id", temas["tema_id"].tolist(), key="del_tema_id")
        if st.button("Excluir Tema"):
            deps = _collect_dependency_messages(
                conn,
                [
                    (
                        "Tópicos vinculados",
                        "SELECT topico_id FROM topico WHERE tema_id=? ORDER BY topico_id",
                        (tema_del,),
                        0,
                    ),
                    (
                        "Pesos de tema em questionários",
                        "SELECT questionario_id FROM peso_tema WHERE tema_id=? ORDER BY questionario_id",
                        (tema_del,),
                        0,
                    ),
                    (
                        "Recomendações por questionário",
                        "SELECT questionario_id FROM recomendacao_tema WHERE tema_id=? ORDER BY questionario_id",
                        (tema_del,),
                        0,
                    ),
                    (
                        "Recomendações default",
                        "SELECT nivel FROM recomendacao_tema_default WHERE tema_id=? ORDER BY nivel",
                        (tema_del,),
                        0,
                    ),
                ],
            )
            if deps:
                st.error(f"Não é possível excluir o tema '{tema_del}' porque há dependências:")
                st.markdown("\n".join(deps))
                return
            conn.execute("DELETE FROM tema WHERE tema_id=?", (tema_del,))
            conn.commit()
            _bump_cache_ver()
            _set_crud_sec_next("Temas")
            st.success(f"Tema {tema_del} excluído.")
            st.rerun()


def _render_crud_topico(conn):
    st.markdown("### CRUD Tópico (MVP)")

    temas = load_table_df(conn, "tema")
    tema_opts = temas["tema_id"].tolist() if not temas.empty else []
    tema_set = set(tema_opts)

    topicos = load_table_df(conn, "topico")
    if topicos.empty:
        topicos = pd.DataFrame(columns=["topico_id", "tema_id", "codigo", "nome", "descricao", "peso_default"])

    topicos = topicos[["topico_id", "tema_id", "codigo", "nome", "descricao", "peso_default"]].copy()

    with st.form("crud_topico_form"):
        topicos_edit = st.data_editor(
            topicos,
            hide_index=True,
            use_container_width=True,
            num_rows="dynamic",
            column_config={
                "topico_id": st.column_config.TextColumn("topico_id"),
                "tema_id": st.column_config.SelectboxColumn("tema_id", options=tema_opts),
                "peso_default": st.column_config.NumberColumn("peso_default", min_value=1, max_value=10, step=1),
            },
            key="crud_topico_editor",
        )
        save_topicos = st.form_submit_button("Salvar alterações de Tópicos")

    if save_topicos:
        try:
            existing_ids = _get_existing_ids(conn, "topico", "topico_id")
            for _, r in topicos_edit.iterrows():
                topico_id = str(r.get("topico_id", "") or "").strip()
                if not topico_id:
                    continue
                tema_id = str(r.get("tema_id", "") or "").strip()
                if tema_id not in tema_set:
                    raise ValueError(f"tema_id inválido em Tópicos: '{tema_id}'. Selecione um tema existente.")
                codigo = str(r.get("codigo", "") or "").strip() or topico_id
                nome = str(r.get("nome", "") or "").strip()
                descricao = str(r.get("descricao", "") or "").strip()
                peso = _w_1a10(r.get("peso_default", 1))
                if not nome:
                    raise ValueError(f"nome obrigatório para topico_id '{topico_id}'.")

                if topico_id in existing_ids:
                    conn.execute(
                        """
                        UPDATE topico
                        SET tema_id=?, codigo=?, nome=?, descricao=?, peso_default=?
                        WHERE topico_id=?
                        """,
                        (tema_id, codigo, nome, descricao, peso, topico_id),
                    )
                else:
                    conn.execute(
                        """
                        INSERT INTO topico (topico_id, tema_id, codigo, nome, descricao, peso_default)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (topico_id, tema_id, codigo, nome, descricao, peso),
                    )
                    existing_ids.add(topico_id)
            conn.commit()
            _bump_cache_ver()
            _set_crud_sec_next("Tópicos")
            st.success("Tópicos atualizados.")
            st.rerun()
        except Exception as e:
            _safe_rollback(conn)
            st.error(f"Erro ao salvar tópicos: {_friendly_db_error(e)}")

    if not topicos.empty:
        topico_del = st.selectbox("Excluir topico_id", topicos["topico_id"].tolist(), key="del_topico_id")
        if st.button("Excluir Tópico"):
            deps = _collect_dependency_messages(
                conn,
                [
                    (
                        "Indicadores vinculados",
                        "SELECT indicador_id FROM indicador WHERE topico_id=? ORDER BY indicador_id",
                        (topico_del,),
                        0,
                    ),
                    (
                        "Pesos de tópico em questionários",
                        "SELECT questionario_id FROM peso_topico WHERE topico_id=? ORDER BY questionario_id",
                        (topico_del,),
                        0,
                    ),
                ],
            )
            if deps:
                st.error(f"Não é possível excluir o tópico '{topico_del}' porque há dependências:")
                st.markdown("\n".join(deps))
                return
            try:
                conn.execute("DELETE FROM topico WHERE topico_id=?", (topico_del,))
                conn.commit()
                _bump_cache_ver()
                _set_crud_sec_next("Tópicos")
                st.success(f"Tópico {topico_del} excluído.")
                st.rerun()
            except Exception as e:
                _safe_rollback(conn)
                st.error(f"Erro ao excluir tópico: {_friendly_db_error(e)}")


def _parse_bool01(x):
    if isinstance(x, bool):
        return 1 if x else 0
    try:
        return 1 if int(float(str(x).strip())) else 0
    except Exception:
        s = str(x).strip().lower()
        return 1 if s in {"1", "true", "sim", "yes", "y"} else 0


def _render_crud_indicador(conn):
    st.markdown("### CRUD Indicador (MVP)")

    topicos = load_table_df(conn, "topico")
    topico_opts = topicos["topico_id"].tolist() if not topicos.empty else []
    topico_set = set(topico_opts)

    indicadores = load_table_df(conn, "indicador")
    if indicadores.empty:
        indicadores = pd.DataFrame(
            columns=[
                "indicador_id",
                "topico_id",
                "codigo",
                "nome",
                "descricao",
                "tipo_indicador",
                "psr_tipo",
                "formula",
                "unidade_resultado",
                "peso_default",
            ]
        )

    indicadores = indicadores[
        [
            "indicador_id",
            "topico_id",
            "codigo",
            "nome",
            "descricao",
            "tipo_indicador",
            "psr_tipo",
            "formula",
            "unidade_resultado",
            "peso_default",
        ]
    ].copy()

    with st.form("crud_indicador_form"):
        indicadores_edit = st.data_editor(
            indicadores,
            hide_index=True,
            use_container_width=True,
            num_rows="dynamic",
            column_config={
                "indicador_id": st.column_config.TextColumn("indicador_id"),
                "topico_id": st.column_config.SelectboxColumn("topico_id", options=topico_opts),
                "tipo_indicador": st.column_config.SelectboxColumn("tipo_indicador", options=["DIRETO", "CALCULADO"]),
                "psr_tipo": st.column_config.SelectboxColumn("psr_tipo", options=["", "PRESSAO", "ESTADO", "RESPOSTA"]),
                "peso_default": st.column_config.NumberColumn("peso_default", min_value=1, max_value=10, step=1),
            },
            key="crud_indicador_editor",
        )
        save_indicadores = st.form_submit_button("Salvar alterações de Indicadores")

    if save_indicadores:
        try:
            existing_ids = _get_existing_ids(conn, "indicador", "indicador_id")
            for _, r in indicadores_edit.iterrows():
                indicador_id = str(r.get("indicador_id", "") or "").strip()
                if not indicador_id:
                    continue
                psr = str(r.get("psr_tipo", "") or "").strip().upper()
                topico_id = str(r.get("topico_id", "") or "").strip()
                if topico_id not in topico_set:
                    raise ValueError(f"topico_id inválido em Indicadores: '{topico_id}'. Selecione um tópico existente.")
                codigo = str(r.get("codigo", "") or "").strip() or indicador_id
                nome = str(r.get("nome", "") or "").strip()
                descricao = str(r.get("descricao", "") or "").strip()
                tipo_ind = str(r.get("tipo_indicador", "DIRETO") or "DIRETO").strip().upper()
                formula = str(r.get("formula", "") or "").strip()
                unidade = str(r.get("unidade_resultado", "") or "").strip()
                peso = _w_1a10(r.get("peso_default", 1))
                if not nome:
                    raise ValueError(f"nome obrigatório para indicador_id '{indicador_id}'.")

                if indicador_id in existing_ids:
                    conn.execute(
                        """
                        UPDATE indicador
                        SET topico_id=?, codigo=?, nome=?, descricao=?, tipo_indicador=?, psr_tipo=?, formula=?, unidade_resultado=?, peso_default=?
                        WHERE indicador_id=?
                        """,
                        (topico_id, codigo, nome, descricao, tipo_ind, (psr or None), formula, unidade, peso, indicador_id),
                    )
                else:
                    conn.execute(
                        """
                        INSERT INTO indicador (indicador_id, topico_id, codigo, nome, descricao, tipo_indicador, psr_tipo, formula, unidade_resultado, peso_default)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (indicador_id, topico_id, codigo, nome, descricao, tipo_ind, (psr or None), formula, unidade, peso),
                    )
                    existing_ids.add(indicador_id)
            conn.commit()
            _bump_cache_ver()
            _set_crud_sec_next("Indicadores")
            st.success("Indicadores atualizados.")
            st.rerun()
        except Exception as e:
            _safe_rollback(conn)
            st.error(f"Erro ao salvar indicadores: {_friendly_db_error(e)}")

    if not indicadores.empty:
        indicador_del = st.selectbox("Excluir indicador_id", indicadores["indicador_id"].tolist(), key="del_indicador_id")
        if st.button("Excluir Indicador"):
            deps = _collect_dependency_messages(
                conn,
                [
                    (
                        "Variáveis vinculadas",
                        "SELECT variavel_id FROM indicador_variavel WHERE indicador_id=? ORDER BY variavel_id",
                        (indicador_del,),
                        0,
                    ),
                    (
                        "Configuração em questionários",
                        "SELECT questionario_id FROM indicador_config WHERE indicador_id=? ORDER BY questionario_id",
                        (indicador_del,),
                        0,
                    ),
                    (
                        "Faixas de referência",
                        "SELECT questionario_id FROM faixa_referencia WHERE indicador_id=? ORDER BY questionario_id",
                        (indicador_del,),
                        0,
                    ),
                ],
            )
            if deps:
                st.error(f"Não é possível excluir o indicador '{indicador_del}' porque há dependências:")
                st.markdown("\n".join(deps))
                return
            try:
                conn.execute("DELETE FROM indicador WHERE indicador_id=?", (indicador_del,))
                conn.commit()
                _bump_cache_ver()
                _set_crud_sec_next("Indicadores")
                st.success(f"Indicador {indicador_del} excluído.")
                st.rerun()
            except Exception as e:
                _safe_rollback(conn)
                st.error(f"Erro ao excluir indicador: {_friendly_db_error(e)}")


def _render_crud_variavel(conn):
    st.markdown("### CRUD Variável (MVP)")

    variaveis = load_table_df(conn, "variavel")
    if variaveis.empty:
        variaveis = pd.DataFrame(
            columns=[
                "variavel_id",
                "codigo",
                "pergunta_texto",
                "descricao",
                "tipo_resposta",
                "unidade_entrada",
                "observacoes",
            ]
        )

    variaveis = variaveis[
        ["variavel_id", "codigo", "pergunta_texto", "descricao", "tipo_resposta", "unidade_entrada", "observacoes"]
    ].copy()

    tipo_opts = ["MULTIPLA_5", "SIM_NAO", "SIM_IMPLANTACAO_NAO", "NUMERICA"]

    with st.form("crud_variavel_form"):
        variaveis_edit = st.data_editor(
            variaveis,
            hide_index=True,
            use_container_width=True,
            num_rows="dynamic",
            column_config={
                "variavel_id": st.column_config.TextColumn("variavel_id"),
                "tipo_resposta": st.column_config.SelectboxColumn("tipo_resposta", options=tipo_opts),
            },
            key="crud_variavel_editor",
        )
        save_variaveis = st.form_submit_button("Salvar alterações de Variáveis")

    if save_variaveis:
        try:
            existing_ids = _get_existing_ids(conn, "variavel", "variavel_id")
            for _, r in variaveis_edit.iterrows():
                variavel_id = str(r.get("variavel_id", "") or "").strip()
                if not variavel_id:
                    continue
                codigo = str(r.get("codigo", "") or "").strip() or variavel_id
                pergunta = str(r.get("pergunta_texto", "") or "").strip()
                descricao = str(r.get("descricao", "") or "").strip()
                tipo = str(r.get("tipo_resposta", "NUMERICA") or "NUMERICA").strip().upper()
                unidade = str(r.get("unidade_entrada", "") or "").strip()
                obs = str(r.get("observacoes", "") or "").strip()
                if not pergunta:
                    raise ValueError(f"pergunta_texto obrigatório para variavel_id '{variavel_id}'.")

                if variavel_id in existing_ids:
                    conn.execute(
                        """
                        UPDATE variavel
                        SET codigo=?, pergunta_texto=?, descricao=?, tipo_resposta=?, unidade_entrada=?, observacoes=?
                        WHERE variavel_id=?
                        """,
                        (codigo, pergunta, descricao, tipo, unidade, obs, variavel_id),
                    )
                else:
                    conn.execute(
                        """
                        INSERT INTO variavel (variavel_id, codigo, pergunta_texto, descricao, tipo_resposta, unidade_entrada, observacoes)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (variavel_id, codigo, pergunta, descricao, tipo, unidade, obs),
                    )
                    existing_ids.add(variavel_id)
            conn.commit()
            _bump_cache_ver()
            _set_crud_sec_next("Variáveis")
            st.success("Variáveis atualizadas.")
            st.rerun()
        except Exception as e:
            _safe_rollback(conn)
            st.error(f"Erro ao salvar variáveis: {_friendly_db_error(e)}")

    if not variaveis.empty:
        variavel_del = st.selectbox("Excluir variavel_id", variaveis["variavel_id"].tolist(), key="del_variavel_id")
        if st.button("Excluir Variável"):
            deps = _collect_dependency_messages(
                conn,
                [
                    (
                        "Indicadores vinculados",
                        "SELECT indicador_id FROM indicador_variavel WHERE variavel_id=? ORDER BY indicador_id",
                        (variavel_del,),
                        0,
                    ),
                    (
                        "Opções de resposta",
                        "SELECT ordem FROM variavel_opcao WHERE variavel_id=? ORDER BY ordem",
                        (variavel_del,),
                        0,
                    ),
                ],
            )
            if deps:
                st.error(f"Não é possível excluir a variável '{variavel_del}' porque há dependências:")
                st.markdown("\n".join(deps))
                return
            try:
                conn.execute("DELETE FROM variavel WHERE variavel_id=?", (variavel_del,))
                conn.commit()
                _bump_cache_ver()
                _set_crud_sec_next("Variáveis")
                st.success(f"Variável {variavel_del} excluída.")
                st.rerun()
            except Exception as e:
                _safe_rollback(conn)
                st.error(f"Erro ao excluir variável: {_friendly_db_error(e)}")


def _render_crud_indicador_variavel(conn):
    st.markdown("### Relação Indicador x Variável (indicador_variavel)")

    indicadores = load_table_df(conn, "indicador")
    variaveis = load_table_df(conn, "variavel")
    indicador_opts = indicadores["indicador_id"].tolist() if not indicadores.empty else []
    variavel_opts = variaveis["variavel_id"].tolist() if not variaveis.empty else []
    indicador_set = set(indicador_opts)
    variavel_set = set(variavel_opts)

    rel = load_table_df(conn, "indicador_variavel")
    if rel.empty:
        rel = pd.DataFrame(columns=["indicador_id", "variavel_id", "papel", "obrigatoria", "peso"])

    rel = rel[["indicador_id", "variavel_id", "papel", "obrigatoria", "peso"]].copy()

    with st.form("crud_ind_var_form"):
        rel_edit = st.data_editor(
            rel,
            hide_index=True,
            use_container_width=True,
            num_rows="dynamic",
            column_config={
                "indicador_id": st.column_config.SelectboxColumn("indicador_id", options=indicador_opts),
                "variavel_id": st.column_config.SelectboxColumn("variavel_id", options=variavel_opts),
                "papel": st.column_config.SelectboxColumn("papel", options=["ENTRADA", "AUXILIAR"]),
                "obrigatoria": st.column_config.NumberColumn("obrigatoria", min_value=0, max_value=1, step=1),
                "peso": st.column_config.NumberColumn("peso", min_value=1, max_value=10, step=1),
            },
            key="crud_ind_var_editor",
        )
        save_rel = st.form_submit_button("Salvar alterações de Relações")

    if save_rel:
        try:
            existing_pairs = {(str(r[0]).strip(), str(r[1]).strip()) for r in conn.execute("SELECT indicador_id, variavel_id FROM indicador_variavel").fetchall()}
            for _, r in rel_edit.iterrows():
                indicador_id = str(r.get("indicador_id", "") or "").strip()
                variavel_id = str(r.get("variavel_id", "") or "").strip()
                if not indicador_id or not variavel_id:
                    continue
                if indicador_id not in indicador_set:
                    raise ValueError(f"indicador_id inválido em Relações: '{indicador_id}'.")
                if variavel_id not in variavel_set:
                    raise ValueError(f"variavel_id inválido em Relações: '{variavel_id}'.")

                peso = r.get("peso")
                if peso is None or str(peso).strip() == "":
                    peso_val = None
                else:
                    peso_val = _w_1a10(peso)

                papel = str(r.get("papel", "ENTRADA") or "ENTRADA").strip().upper()
                obrig = _parse_bool01(r.get("obrigatoria", 1))
                pair = (indicador_id, variavel_id)
                if pair in existing_pairs:
                    conn.execute(
                        """
                        UPDATE indicador_variavel
                        SET papel=?, obrigatoria=?, peso=?
                        WHERE indicador_id=? AND variavel_id=?
                        """,
                        (papel, obrig, peso_val, indicador_id, variavel_id),
                    )
                else:
                    conn.execute(
                        """
                        INSERT INTO indicador_variavel (indicador_id, variavel_id, papel, obrigatoria, peso)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (indicador_id, variavel_id, papel, obrig, peso_val),
                    )
                    existing_pairs.add(pair)
            conn.commit()
            _bump_cache_ver()
            _set_crud_sec_next("Indicador x Variável")
            st.success("Relações atualizadas.")
            st.rerun()
        except Exception as e:
            _safe_rollback(conn)
            st.error(f"Erro ao salvar relações: {_friendly_db_error(e)}")

    if not indicador_opts or not variavel_opts:
        st.warning("Crie pelo menos um indicador e uma variável antes de editar relações.")

    if not rel.empty:
        rel_pairs = [f"{i['indicador_id']} | {i['variavel_id']}" for _, i in rel.iterrows()]
        rel_del = st.selectbox("Excluir relação", rel_pairs, key="del_rel_pair")
        if st.button("Excluir Relação"):
            try:
                indicador_id, variavel_id = [s.strip() for s in rel_del.split("|", 1)]
                conn.execute(
                    "DELETE FROM indicador_variavel WHERE indicador_id=? AND variavel_id=?",
                    (indicador_id, variavel_id),
                )
                conn.commit()
                _bump_cache_ver()
                _set_crud_sec_next("Indicador x Variável")
                st.success(f"Relação {indicador_id} x {variavel_id} excluída.")
                st.rerun()
            except Exception as e:
                _safe_rollback(conn)
                st.error(f"Erro ao excluir relação: {_friendly_db_error(e)}")


def _render_crud_macrobase(conn):
    st.subheader("Manutenção da Macro-base (CRUD inicial)")
    st.caption("MVP com CRUD de Eixo, Tema, Tópico, Indicador, Variável e vínculo indicador_variavel.")

    next_sec = st.session_state.pop("crud_macrobase_sec_next", None)
    if next_sec is not None:
        st.session_state["crud_macrobase_sec"] = next_sec

    secao = st.radio(
        "Seção do CRUD",
        ["Eixos", "Temas", "Tópicos", "Indicadores", "Variáveis", "Indicador x Variável"],
        horizontal=True,
        key="crud_macrobase_sec",
    )

    if secao == "Eixos":
        _render_crud_eixo(conn)
    elif secao == "Temas":
        _render_crud_tema(conn)
    elif secao == "Tópicos":
        _render_crud_topico(conn)
    elif secao == "Indicadores":
        _render_crud_indicador(conn)
    elif secao == "Variáveis":
        _render_crud_variavel(conn)
    else:
        _render_crud_indicador_variavel(conn)


def render_macrobase_editor(conn):
    st.header("Macro-base (Turso) — v2.1")

    with st.expander("Exportar macro-base atual (Turso -> Excel)", expanded=False):
        st.caption("Baixa um arquivo completo da macro-base atual sem alterar nenhum dado no Turso.")
        if st.button("Gerar arquivo da macro-base atual", key="btn_export_macrobase"):
            try:
                payload = export_macrobase_xlsx(conn)
                st.download_button(
                    "Baixar macro-base atualizada (.xlsx)",
                    data=payload,
                    file_name="macro-base-2.1-atualizada.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="download_macrobase_xlsx",
                )
                st.success("Arquivo gerado. Clique em 'Baixar macro-base atualizada (.xlsx)'.")
            except Exception as e:
                st.error(f"Erro ao gerar arquivo da macro-base: {_friendly_db_error(e)}")

    if "macrobase_upload_unlocked" not in st.session_state:
        st.session_state["macrobase_upload_unlocked"] = False

    modo = st.radio(
        "Modo",
        ["CRUD Macro-base (MVP)", "Carga via planilha"],
        index=0,
        horizontal=True,
        key="macrobase_modo",
    )

    if modo == "Carga via planilha":
        st.info("A carga via planilha é protegida por senha para evitar alterações acidentais.")

        if not st.session_state.get("macrobase_upload_unlocked", False):
            with st.form("macrobase_upload_password_form"):
                pwd = st.text_input("Senha para habilitar carga via planilha", type="password", key="macrobase_upload_pwd")
                unlock = st.form_submit_button("Desbloquear")

            if unlock:
                if (pwd or "").strip() == "sorg":
                    st.session_state["macrobase_upload_unlocked"] = True
                    st.success("Carga via planilha desbloqueada.")
                    st.rerun()
                else:
                    st.error("Senha inválida.")
            return

        if st.button("Bloquear carga via planilha", key="lock_macrobase_upload"):
            st.session_state["macrobase_upload_unlocked"] = False
            st.success("Carga via planilha bloqueada.")
            st.rerun()

        uploaded_file = st.file_uploader("Carregar arquivo MACRO_BASE_v2_1.xlsx", type=["xlsx"])

        if uploaded_file:
            data = load_macrobase(uploaded_file)

            st.subheader("Pré-visualização do Excel")
            for k in data.keys():
                st.write(f"**{k}**")
                st.dataframe(data[k], use_container_width=True)

            if st.button("Publicar macro-base no Turso (schema v2.1)"):
                with st.spinner("Gravando no Turso..."):
                    publish_macrobase_relacional_v21(conn, data)
                _bump_cache_ver()
                st.success("Macro-base publicada no Turso! ✅")

        st.divider()
        st.subheader("Visualização das tabelas no Turso")
        for table in [
            "eixo",
            "tema",
            "topico",
            "indicador",
            "variavel",
            "variavel_opcao",
            "indicador_variavel",
            "recomendacao_tema_default",
            "recomendacao_eixo_default",
        ]:
            with st.expander(table, expanded=False):
                try:
                    df = load_table_df(conn, table)
                    st.dataframe(df, use_container_width=True)
                except Exception as e:
                    st.info(f"Não consegui ler {table}: {e}")
    else:
        _render_crud_macrobase(conn)

def publish_macrobase_relacional_v21(conn, data: dict):
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.sync()

    # helpers
    def sid(x): return str(x).strip() if x is not None else ""
    def stext(x): return "" if pd.isna(x) else str(x).strip()

    def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        out.columns = [str(c).strip().upper() for c in out.columns]
        return out

    def _pick_value(row, *candidates):
        for col in candidates:
            if col in row and not pd.isna(row[col]):
                val = str(row[col]).strip()
                if val != "":
                    return val
        return ""

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
    conn.execute("DELETE FROM recomendacao_tema_default;")
    conn.execute("DELETE FROM recomendacao_eixo_default;")
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

    # RECOMENDACAO_TEMA_DEFAULT (opcional no arquivo)
    if "RECOMENDACAO_TEMA_DEFAULT" in data:
        df = _normalize_columns(data["RECOMENDACAO_TEMA_DEFAULT"].fillna(""))
        for _, r in df.iterrows():
            tema_id = _pick_value(r, "TEMA_ID")
            if not tema_id:
                continue
            nivel_raw = _pick_value(r, "NIVEL")
            if not nivel_raw:
                continue
            recomendacao = _pick_value(r, "RECOMENDACAO", "TEXTO")
            if not recomendacao:
                continue
            conn.execute(
                "INSERT INTO recomendacao_tema_default (tema_id, nivel, recomendacao) VALUES (?, ?, ?)",
                (tema_id, int(float(str(nivel_raw).replace(",", "."))), recomendacao),
            )

    # RECOMENDACAO_EIXO_DEFAULT (opcional no arquivo)
    if "RECOMENDACAO_EIXO_DEFAULT" in data:
        df = _normalize_columns(data["RECOMENDACAO_EIXO_DEFAULT"].fillna(""))
        for _, r in df.iterrows():
            eixo_id = _pick_value(r, "EIXO_ID")
            if not eixo_id:
                continue
            nivel_raw = _pick_value(r, "NIVEL")
            if not nivel_raw:
                continue
            recomendacao = _pick_value(r, "RECOMENDACAO", "TEXTO")
            if not recomendacao:
                continue
            conn.execute(
                "INSERT INTO recomendacao_eixo_default (eixo_id, nivel, recomendacao) VALUES (?, ?, ?)",
                (eixo_id, int(float(str(nivel_raw).replace(",", "."))), recomendacao),
            )

    conn.commit()
    conn.sync()

def load_table_df(conn, table: str) -> pd.DataFrame:
    cur = conn.execute(f"SELECT * FROM {table};")
    rows = cur.fetchall()
    cols = [d[0] for d in cur.description] if cur.description else []
    return pd.DataFrame(rows, columns=cols)
