import pandas as pd

def load_macrobase(file):
    xls = pd.ExcelFile(file)

    data = {
        "EIXOS": pd.read_excel(file, sheet_name="EIXOS"),
        "TEMAS": pd.read_excel(file, sheet_name="TEMAS"),
        "TOPICOS": pd.read_excel(file, sheet_name="TOPICOS"),
        "INDICADORES": pd.read_excel(file, sheet_name="INDICADORES"),
        "VARIAVEIS": pd.read_excel(file, sheet_name="VARIAVEIS"),
        "VARIAVEL_OPCOES": pd.read_excel(file, sheet_name="VARIAVEL_OPCOES"),
        "INDICADOR_VARIAVEL": pd.read_excel(file, sheet_name="INDICADOR_VARIAVEL"),
    }

    optional_aliases = {
        "RECOMENDACAO_TEMA_DEFAULT": ["RECOMENDACAO_TEMA_DEFAULT", "RECOM_TEMA_DEFAULT"],
        "RECOMENDACAO_EIXO_DEFAULT": ["RECOMENDACAO_EIXO_DEFAULT", "RECOM_EIXO_DEFAULT"],
    }

    available = set(xls.sheet_names)
    for key, aliases in optional_aliases.items():
        chosen = next((name for name in aliases if name in available), None)
        if chosen:
            data[key] = pd.read_excel(file, sheet_name=chosen)

    return data
