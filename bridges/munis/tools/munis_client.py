"""
Tyler Munis ERP -- ODBC Client for SQL Server

Read-only ODBC client for the cloud-hosted Munis database. Provides
authenticated access via Microsoft ODBC Driver 18 with TLS, read-only
enforcement at both the connection and application layers, and safe
type serialization for JSON output.

Tyler Munis exposes reporting data through table-valued functions in
dedicated *ReportingServices schemas (e.g. GeneralLedgerReportingServices).
Most functions require a @UserName parameter (the SQL login name) that
controls row-level access based on the Munis application user profile.

Environment variables (per-operator, injected by Tendril Root):
  MUNIS_DB_HOST      SQL Server hostname (shared, from docker-compose)
  MUNIS_DB_NAME      Database name (shared, from docker-compose)
  MUNIS_DB_USER      Per-operator SQL username (from credential vault)
  MUNIS_DB_PASSWORD  Per-operator SQL password (from credential vault)
"""

import os
import sys
import json
import re
from datetime import date, datetime, time
from decimal import Decimal

try:
    import pyodbc
except ImportError:
    print(
        "ERROR: pyodbc is not installed.\n"
        "  pip install pyodbc\n",
        file=sys.stderr,
    )
    sys.exit(1)

DRIVER = "{ODBC Driver 18 for SQL Server}"

BLOCKED_KEYWORDS = re.compile(
    r"^\s*(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|EXEC|EXECUTE|MERGE|GRANT|REVOKE|DENY)\b",
    re.IGNORECASE,
)

DEFAULT_ROW_LIMIT = 1000
CONNECT_TIMEOUT = 15
QUERY_TIMEOUT = 120


def _env(name: str, required: bool = True) -> str:
    val = os.getenv(name, "").strip()
    if required and not val:
        print(f"ERROR: Missing required environment variable: {name}", file=sys.stderr)
        sys.exit(1)
    return val


def _serialize(value):
    """Convert DB types to JSON-safe Python types."""
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, time):
        return value.isoformat()
    if isinstance(value, bytes):
        return value.hex()
    return value


class MunisClient:
    """Read-only ODBC client for Tyler Munis SQL Server."""

    def __init__(
        self,
        host: str = None,
        database: str = None,
        user: str = None,
        password: str = None,
    ):
        self.host = host or _env("MUNIS_DB_HOST")
        self.database = database or _env("MUNIS_DB_NAME")
        self.user = user or _env("MUNIS_DB_USER")
        self.password = password or _env("MUNIS_DB_PASSWORD")
        self._conn = None

    @property
    def connection_string(self) -> str:
        return (
            f"DRIVER={DRIVER};"
            f"SERVER={self.host};"
            f"DATABASE={self.database};"
            f"UID={self.user};"
            f"PWD={self.password};"
            f"Encrypt=yes;"
            f"TrustServerCertificate=yes;"
            f"ApplicationIntent=ReadOnly;"
            f"Connection Timeout={CONNECT_TIMEOUT};"
        )

    def connect(self) -> pyodbc.Connection:
        if self._conn is None:
            self._conn = pyodbc.connect(self.connection_string, timeout=CONNECT_TIMEOUT)
            self._conn.timeout = QUERY_TIMEOUT
        return self._conn

    def close(self):
        if self._conn:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *exc):
        self.close()

    @staticmethod
    def validate_readonly(sql: str):
        """Reject any statement that is not a SELECT or WITH (CTE)."""
        stripped = sql.strip()
        if BLOCKED_KEYWORDS.match(stripped):
            raise PermissionError(
                f"Write operations are not permitted. "
                f"Only SELECT and WITH (CTE) queries are allowed."
            )
        leading = stripped.split()[0].upper() if stripped else ""
        if leading not in ("SELECT", "WITH"):
            raise PermissionError(
                f"Unsupported statement type: '{leading}'. "
                f"Only SELECT and WITH (CTE) queries are allowed."
            )

    def execute_query(
        self, sql: str, params: tuple = None, limit: int = DEFAULT_ROW_LIMIT
    ) -> dict:
        """Execute a read-only SQL query and return results as a dict."""
        self.validate_readonly(sql)
        conn = self.connect()
        cursor = conn.cursor()

        if params:
            cursor.execute(sql, params)
        else:
            cursor.execute(sql)

        if cursor.description is None:
            return {"columns": [], "rows": [], "row_count": 0, "truncated": False}

        columns = [col[0] for col in cursor.description]
        rows_raw = cursor.fetchmany(limit + 1)
        truncated = len(rows_raw) > limit
        if truncated:
            rows_raw = rows_raw[:limit]

        rows = []
        for row in rows_raw:
            rows.append({col: _serialize(val) for col, val in zip(columns, row)})

        cursor.close()
        return {
            "columns": columns,
            "rows": rows,
            "row_count": len(rows),
            "truncated": truncated,
        }

    def list_tables(self, schema: str = None, filter_name: str = None) -> list[dict]:
        """List tables and views in the database."""
        sql = "SELECT TABLE_SCHEMA, TABLE_NAME, TABLE_TYPE FROM INFORMATION_SCHEMA.TABLES WHERE 1=1"
        params = []
        if schema:
            sql += " AND TABLE_SCHEMA = ?"
            params.append(schema)
        if filter_name:
            sql += " AND TABLE_NAME LIKE ?"
            params.append(filter_name)
        sql += " ORDER BY TABLE_SCHEMA, TABLE_NAME"

        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute(sql, params)
        results = [{"schema": r[0], "name": r[1], "type": r[2]} for r in cursor.fetchall()]
        cursor.close()
        return results

    def list_functions(self, schema: str = None) -> list[dict]:
        """List table-valued functions in the ReportingServices schemas."""
        sql = "SELECT r.ROUTINE_SCHEMA, r.ROUTINE_NAME, r.DATA_TYPE FROM INFORMATION_SCHEMA.ROUTINES r WHERE r.DATA_TYPE = 'TABLE'"
        params = []
        if schema:
            sql += " AND r.ROUTINE_SCHEMA = ?"
            params.append(schema)
        else:
            sql += " AND r.ROUTINE_SCHEMA LIKE '%ReportingServices'"
        sql += " ORDER BY r.ROUTINE_SCHEMA, r.ROUTINE_NAME"

        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute(sql, params)
        results = [{"schema": r[0], "name": r[1], "return_type": r[2]} for r in cursor.fetchall()]
        cursor.close()
        return results

    def describe_function(self, name: str, schema: str) -> dict:
        """Describe a table-valued function's parameters and return columns."""
        conn = self.connect()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT PARAMETER_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH "
            "FROM INFORMATION_SCHEMA.PARAMETERS "
            "WHERE SPECIFIC_SCHEMA = ? AND SPECIFIC_NAME = ? "
            "AND PARAMETER_NAME IS NOT NULL ORDER BY ORDINAL_POSITION",
            (schema, name),
        )
        params = [{"name": r[0], "type": r[1], "max_length": r[2]} for r in cursor.fetchall()]

        columns = []
        try:
            args = ", ".join(["NULL"] * len(params))
            cursor.execute(f"SELECT TOP 0 * FROM [{schema}].[{name}]({args})")
            columns = [col[0] for col in cursor.description]
        except Exception:
            pass

        cursor.close()
        if not params and not columns:
            raise ValueError(f"Function '{schema}.{name}' not found.")
        return {"schema": schema, "name": name, "parameters": params, "columns": columns}

    def describe_table(self, table: str, schema: str = "dbo") -> list[dict]:
        """Describe columns for a table or view."""
        sql = (
            "SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH, "
            "NUMERIC_PRECISION, NUMERIC_SCALE, IS_NULLABLE, COLUMN_DEFAULT "
            "FROM INFORMATION_SCHEMA.COLUMNS "
            "WHERE TABLE_SCHEMA = ? AND TABLE_NAME = ? ORDER BY ORDINAL_POSITION"
        )
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute(sql, (schema, table))
        results = [
            {"column": r[0], "type": r[1], "max_length": r[2], "precision": r[3],
             "scale": r[4], "nullable": r[5], "default": r[6]}
            for r in cursor.fetchall()
        ]
        cursor.close()
        if not results:
            raise ValueError(f"Table '{schema}.{table}' not found or has no columns.")
        return results

    def test_connection(self) -> dict:
        """Validate connectivity and return server metadata."""
        try:
            conn = self.connect()
            cursor = conn.cursor()
            cursor.execute("SELECT @@VERSION")
            version = cursor.fetchone()[0]
            cursor.execute("SELECT DB_NAME()")
            db_name = cursor.fetchone()[0]
            cursor.execute(
                "SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES "
                "WHERE TABLE_TYPE IN ('BASE TABLE', 'VIEW')"
            )
            table_count = cursor.fetchone()[0]
            cursor.close()
            return {
                "ok": True,
                "server_version": version.split("\n")[0].strip(),
                "database": db_name,
                "table_count": table_count,
            }
        except pyodbc.Error as e:
            return {"ok": False, "error": str(e)}
        except Exception as e:
            return {"ok": False, "error": str(e)}


if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "test"
    client = MunisClient()

    if action == "test":
        result = client.test_connection()
        print(json.dumps(result, indent=2))
    else:
        print(f"Unknown action: {action}")
        print("Usage: python3 munis_client.py [test]")
        sys.exit(1)
