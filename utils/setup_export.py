import io
import pandas as pd
from openpyxl import Workbook
from openpyxl.utils import get_column_letter

def df_from_query(conn, sql: str, params=()):
    cur = conn.execute(sql, params)
    rows = cur.fetchall()
    cols = [d[0] for d in cur.description] if cur.description else []
    return pd.DataFrame(rows, columns=cols)

def autosize(ws, max_width=70):
    for col in range(1, ws.max_column + 1):
        max_len = 0
        for row in range(1, min(ws.max_row, 80) + 1):
            v = ws.cell(row=row, column=col).value
            if v is None:
                continue
            max_len = max(max_len, len(str(v)))
        ws.column_dimensions[get_column_letter(col)].width = min(max(12, max_len + 2), max_width)

def write_df(ws, df):
    ws.append(list(df.columns))
    for r in df.itertuples(index=False, name=None):
        ws.append(list(r))
    ws.freeze_panes = "A2"
    autosize(ws)

def export_setup_xlsx(conn, questionario_id: str) -> bytes:
    wb = Workbook()
    wb.remove(wb.active)

    # CONFIG_DIMENSAO
    ws = wb.create_sheet("CONFIG_DIMENSAO")
    ws["A1"] = "Nome do campo de dimensão"
    ws["A2"] = "EIXO"
    ws["A4"] = "Arquivo gerado pelo Builder (macro-base no Turso)."
    ws.column_dimensions["A"].width = 90

    # LISTAS (opcional, útil para a outra aplicação)
    setores = df_from_query(conn, "SELECT DISTINCT setor FROM questionario WHERE setor IS NOT NULL AND setor <> ''")
    portes = df_from_query(conn, "SELECT DISTINCT porte FROM questionario WHERE porte IS NOT NULL AND porte <> ''")
    regioes = df_from_query(conn, "SELECT DISTINCT regiao FROM questionario WHERE regiao IS NOT NULL AND regiao <> ''")

    wsL = wb.create_sheet("LISTAS")
    wsL["A1"] = "SETORES"
    for i, v in enumerate(setores["setor"].tolist(), start=2):
        wsL[f"A{i}"] = v
    wsL["C1"] = "PORTES"
    for i, v in enumerate(portes["porte"].tolist(), start=2):
        wsL[f"C{i}"] = v
    wsL["E1"] = "REGIOES"
    for i, v in enumerate(regioes["regiao"].tolist(), start=2):
        wsL[f"E{i}"] = v
    autosize(wsL)

    # QUESTIONARIO (apenas o selecionado)
    q = df_from_query(conn, """
        SELECT questionario_id, setor, porte, regiao, versao, status, observacao
        FROM questionario WHERE questionario_id=?
    """, (questionario_id,))
    write_df(wb.create_sheet("QUESTIONARIO"), q)

    # CONFIG_ORGANIZACOES (mantém como você pediu)
    # ATIVO = 1 quando status != ARCHIVED
    cfg = q.copy()
    cfg = cfg.rename(columns={"setor":"SETOR","porte":"PORTE","regiao":"REGIAO","observacao":"OBSERVACAO"})
    cfg["ATIVO"] = cfg["status"].apply(lambda s: 0 if str(s).upper() == "ARCHIVED" else 1)
    cfg = cfg[["SETOR","PORTE","REGIAO","ATIVO","OBSERVACAO"]]
    write_df(wb.create_sheet("CONFIG_ORGANIZACOES"), cfg)

    # PESOS_TEMA / PESOS_TOPICO
    pt = df_from_query(conn, "SELECT questionario_id, tema_id, peso_tema FROM peso_tema WHERE questionario_id=?", (questionario_id,))
    if pt.empty:
        pt = pd.DataFrame(columns=["questionario_id","tema_id","peso_tema"])
    write_df(wb.create_sheet("PESOS_TEMA"), pt)

    ptop = df_from_query(conn, "SELECT questionario_id, topico_id, peso_topico FROM peso_topico WHERE questionario_id=?", (questionario_id,))
    if ptop.empty:
        ptop = pd.DataFrame(columns=["questionario_id","topico_id","peso_topico"])
    write_df(wb.create_sheet("PESOS_TOPICO"), ptop)

    # INDICADORES_SETUP
    ind = df_from_query(conn, """
        SELECT questionario_id, indicador_id, ativo, peso_indicador
        FROM indicador_config
        WHERE questionario_id=?
        ORDER BY indicador_id
    """, (questionario_id,))
    if ind.empty:
        ind = pd.DataFrame(columns=["questionario_id","indicador_id","ativo","peso_indicador"])
    write_df(wb.create_sheet("INDICADORES_SETUP"), ind)

    # FAIXA_REFERENCIA
    fr = df_from_query(conn, """
        SELECT questionario_id, indicador_id, nivel, tipo_regra, valor_min, valor_max, valor_exato, rotulo
        FROM faixa_referencia
        WHERE questionario_id=?
        ORDER BY indicador_id, nivel
    """, (questionario_id,))
    if fr.empty:
        fr = pd.DataFrame(columns=["questionario_id","indicador_id","nivel","tipo_regra","valor_min","valor_max","valor_exato","rotulo"])
    write_df(wb.create_sheet("FAIXA_REFERENCIA"), fr)

    # RECOM_TEMA / RECOM_EIXO
    rt = df_from_query(conn, """
        SELECT questionario_id, tema_id, nivel, recomendacao
        FROM recomendacao_tema
        WHERE questionario_id=?
        ORDER BY tema_id, nivel
    """, (questionario_id,))
    if rt.empty:
        rt = pd.DataFrame(columns=["questionario_id","tema_id","nivel","recomendacao"])
    write_df(wb.create_sheet("RECOM_TEMA"), rt)

    re = df_from_query(conn, """
        SELECT questionario_id, eixo_id, nivel, recomendacao
        FROM recomendacao_eixo
        WHERE questionario_id=?
        ORDER BY eixo_id, nivel
    """, (questionario_id,))
    if re.empty:
        re = pd.DataFrame(columns=["questionario_id","eixo_id","nivel","recomendacao"])
    write_df(wb.create_sheet("RECOM_EIXO"), re)

    ws = wb.create_sheet("README")
    ws["A1"] = "SETUP gerado pelo Builder"
    ws["A3"] = "CONFIG_ORGANIZACOES usa curinga '*' quando aplicável."
    ws["A4"] = "Pesos: inteiros 1..10 (tema/tópico/indicador)."
    ws["A5"] = "Faixas: nível 1..5 por indicador."
    ws.column_dimensions["A"].width = 90

    bio = io.BytesIO()
    wb.save(bio)
    return bio.getvalue()
