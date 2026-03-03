import os
import streamlit as st
import libsql

@st.cache_resource
def get_conn():
    url = st.secrets["libsql://sorg-titetodesco.aws-us-east-1.turso.io"]
    token = st.secrets["eyJhbGciOiJFZERTQSIsInR5cCI6IkpXVCJ9.eyJhIjoicnciLCJpYXQiOjE3NzI0OTkzNTgsImlkIjoiMDE5Y2IxMzEtNzkwMS03YWIwLTg1YjgtMDQ5NzFlZjE0ZDQ5IiwicmlkIjoiNzUwZDdhZTMtYjNiMi00NGY4LWE1OGMtZmM5OGY5ZjAyMjY1In0.amsXjuhaHsN0BtITp5LTLsV2Gw-hwjcZkdREyc6ONVUJ9lYHbfUmG5lTCm0j4WaPTi-1ifss34iNgjKV2JdcBw"]
    conn = libsql.connect("sorg_macrobase.db", sync_url=url, auth_token=token)
    conn.sync()
    return conn

def init_schema(conn, schema_path: str = "schema.sql") -> None:
    # Importante: ligar FK no SQLite
    conn.execute("PRAGMA foreign_keys = ON;")

    with open(schema_path, "r", encoding="utf-8") as f:
        sql = f.read()

    # libsql aceita executar múltiplas instruções via executescript
    # (se sua versão não tiver, eu te mando alternativa com split seguro)
    conn.executescript(sql)

    conn.commit()
    conn.sync()
