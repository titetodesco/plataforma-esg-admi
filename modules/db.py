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
        self._rows = list(getattr(self._result_set, "rows", []))
        self._idx = 0

    def fetchall(self):
        if self._idx == 0:
            self._idx = len(self._rows)
            return list(self._rows)
        if self._idx >= len(self._rows):
            return []
        remaining = self._rows[self._idx :]
        self._idx = len(self._rows)
        return list(remaining)

    def fetchone(self):
        if self._idx >= len(self._rows):
            return None
        row = self._rows[self._idx]
        self._idx += 1
        return row


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
    alias_map = {
        "TURSO_DATABASE_URL": ["TURSO_DATABASE_URL", "DATABASE_URL", "TURSO_URL"],
        "TURSO_AUTH_TOKEN": ["TURSO_AUTH_TOKEN", "AUTH_TOKEN", "TURSO_TOKEN"],
    }

    nested_map = {
        "TURSO_DATABASE_URL": [
            ("turso", "database_url"),
            ("turso", "url"),
            ("database", "url"),
        ],
        "TURSO_AUTH_TOKEN": [
            ("turso", "auth_token"),
            ("turso", "token"),
            ("database", "auth_token"),
        ],
    }

    keys = alias_map.get(name, [name])

    secrets_data = None
    try:
        secrets_data = st.secrets
    except Exception:
        secrets_data = None

    if secrets_data is not None:
        for key in keys:
            if key in secrets_data and str(secrets_data[key]).strip():
                return str(secrets_data[key]).strip()

        for path in nested_map.get(name, []):
            current = secrets_data
            try:
                for part in path:
                    if part not in current:
                        current = None
                        break
                    current = current[part]
                if current is not None and str(current).strip():
                    return str(current).strip()
            except Exception:
                continue

    for key in keys:
        value = os.getenv(key, "").strip()
        if value:
            return value

    return ""

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
