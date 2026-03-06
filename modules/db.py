import os
import time
import streamlit as st

try:
    import libsql  # type: ignore
except Exception:
    libsql = None

try:
    from libsql_client import create_client_sync  # type: ignore
except Exception:
    create_client_sync = None


class ResultSetCursorAdapter:
    def __init__(self, result_set):
        self._result_set = result_set
        self.description = [(c,) for c in tuple(getattr(result_set, "columns", ()))]

    def fetchall(self):
        return list(getattr(self._result_set, "rows", []))


class LibsqlClientConnAdapter:
    def __init__(self, client):
        self._client = client

    def execute(self, sql: str, params=()):
        args = tuple(params) if params is not None else ()
        result_set = self._client.execute(sql, args)
        return ResultSetCursorAdapter(result_set)

    def commit(self):
        return None

    def sync(self):
        return None

def _get_secret(name: str) -> str:
    if name in st.secrets:
        return str(st.secrets[name])
    return os.getenv(name, "")

def _connect():
    url = _get_secret("TURSO_DATABASE_URL")
    token = _get_secret("TURSO_AUTH_TOKEN")

    if not url or not token:
        raise RuntimeError(
            "Turso obrigatório: defina TURSO_DATABASE_URL e TURSO_AUTH_TOKEN em st.secrets ou variáveis de ambiente."
        )

    if libsql is not None:
        return libsql.connect("sorg_macrobase.db", sync_url=url, auth_token=token)

    if create_client_sync is not None:
        client_url = url
        if url.startswith("libsql://"):
            client_url = "https://" + url[len("libsql://"):]
        client = create_client_sync(client_url, auth_token=token)
        return LibsqlClientConnAdapter(client)

    raise RuntimeError(
        "Turso obrigatório: nenhum cliente Turso disponível. Instale libsql-client (ou libsql) no ambiente."
    )

@st.cache_resource
def get_conn():
    conn = _connect()
    conn.sync()
    return conn

def safe_execute(conn, sql: str, params=None, retries: int = 2):
    params = params or ()
    last_err = None
    for _ in range(retries + 1):
        try:
            return conn.execute(sql, params)
        except Exception as e:
            last_err = e
            msg = str(e).lower()
            if "stream not found" in msg or "hrana" in msg:
                try:
                    st.cache_resource.clear()
                except Exception:
                    pass
                time.sleep(0.2)
                conn = get_conn()
                continue
            raise
    raise last_err

def init_schema(conn, schema_path: str = "schema.sql") -> None:
    safe_execute(conn, "PRAGMA foreign_keys = ON;")
    with open(schema_path, "r", encoding="utf-8") as f:
        sql = f.read()
    # split simples por ';' (ok para nosso schema)
    statements = [s.strip() for s in sql.split(";") if s.strip()]
    for stmt in statements:
        safe_execute(conn, stmt + ";")
    conn.sync()
