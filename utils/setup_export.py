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
    conn.sync()  # 1 sync apenas aqui (você já aplicou isso ✅)

    wb = Workbook()
    wb.remove(wb.active)

    # Puxa o questionário (para montar CONFIG_ORGANIZACOES)
    q = df_from_query(conn, """
        SELECT setor, porte, regiao, status, observacao
        FROM questionario
        WHERE questionario_id=?
    """, (questionario_id,))
    if q.empty:
        raise ValueError(f"Questionario_id '{questionario_id}' não encontrado.")

    # CONFIG_ORGANIZACOES
    cfg = q.rename(columns={"setor":"SETOR","porte":"PORTE","regiao":"REGIAO","observacao":"OBSERVACAO"}).copy()
    cfg["ATIVO"] = cfg["status"].apply(lambda s: 0 if str(s).upper() == "ARCHIVED" else 1)
    cfg = cfg[["SETOR","PORTE","REGIAO","ATIVO","OBSERVACAO"]]
    write_df(wb.create_sheet("CONFIG_ORGANIZACOES"), cfg)

    # PESOS_TEMA
    pt = df_from_query(conn, """
        SELECT questionario_id, tema_id, peso_tema
        FROM peso_tema
        WHERE questionario_id=?
        ORDER BY tema_id
    """, (questionario_id,))
    if pt.empty:
        pt = pd.DataFrame(columns=["questionario_id","tema_id","peso_tema"])
    write_df(wb.create_sheet("PESOS_TEMA"), pt)

    # PESOS_TOPICO
    ptop = df_from_query(conn, """
        SELECT questionario_id, topico_id, peso_topico
        FROM peso_topico
        WHERE questionario_id=?
        ORDER BY topico_id
    """, (questionario_id,))
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

    # RECOM_TEMA
    rt = df_from_query(conn, """
        SELECT questionario_id, tema_id, nivel, recomendacao
        FROM recomendacao_tema
        WHERE questionario_id=?
        ORDER BY tema_id, nivel
    """, (questionario_id,))
    if rt.empty:
        rt = pd.DataFrame(columns=["questionario_id","tema_id","nivel","recomendacao"])
    write_df(wb.create_sheet("RECOM_TEMA"), rt)

    # RECOM_EIXO
    re = df_from_query(conn, """
        SELECT questionario_id, eixo_id, nivel, recomendacao
        FROM recomendacao_eixo
        WHERE questionario_id=?
        ORDER BY eixo_id, nivel
    """, (questionario_id,))
    if re.empty:
        re = pd.DataFrame(columns=["questionario_id","eixo_id","nivel","recomendacao"])
    write_df(wb.create_sheet("RECOM_EIXO"), re)

    bio = io.BytesIO()
    wb.save(bio)
    return bio.getvalue()
