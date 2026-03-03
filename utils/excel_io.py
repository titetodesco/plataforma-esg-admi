import pandas as pd

def load_macrobase(file):
    return {
        "EIXOS": pd.read_excel(file, sheet_name="EIXOS"),
        "TEMAS": pd.read_excel(file, sheet_name="TEMAS"),
        "TOPICOS": pd.read_excel(file, sheet_name="TOPICOS"),
        "INDICADORES": pd.read_excel(file, sheet_name="INDICADORES"),
        "VARIAVEIS": pd.read_excel(file, sheet_name="VARIAVEIS"),
        "INDICADOR_VARIAVEL": pd.read_excel(file, sheet_name="INDICADOR_VARIAVEL"),
    }
