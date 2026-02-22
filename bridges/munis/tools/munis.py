#!/usr/bin/env python3
"""
Munis ODBC Bridge -- Unified CLI

Read-only access to the Tyler Munis ERP SQL Server database via the
Tyler Reporting Services table-valued functions.

Usage:
  python3 munis.py query     --sql "SELECT TOP 10 * FROM ..." [--limit N] [--format json|table|csv]
  python3 munis.py tables    [--schema dbo] [--filter "GL%"]
  python3 munis.py functions [--schema GeneralLedgerReportingServices]
  python3 munis.py describe  --table TABLE_NAME [--schema dbo]
  python3 munis.py report    --name REPORT_NAME [--params '{"key":"val"}'] [--limit N] [--format json|table|csv]
  python3 munis.py reports
"""

import argparse
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from munis_client import MunisClient, DEFAULT_ROW_LIMIT


# -- Output Formatters --

def fmt_json(data: dict):
    print(json.dumps(data, indent=2, default=str))


def fmt_table(data: dict):
    columns = data.get("columns", [])
    rows = data.get("rows", [])
    if not columns:
        print("(no results)")
        return

    col_widths = {c: len(c) for c in columns}
    for row in rows:
        for c in columns:
            val = str(row.get(c, ""))
            col_widths[c] = max(col_widths[c], min(len(val), 60))

    header = " | ".join(c.ljust(col_widths[c])[:60] for c in columns)
    sep = "-+-".join("-" * min(col_widths[c], 60) for c in columns)
    print(header)
    print(sep)
    for row in rows:
        line = " | ".join(
            str(row.get(c, "")).ljust(col_widths[c])[:60] for c in columns
        )
        print(line)

    print(f"\n({data.get('row_count', 0)} rows)")
    if data.get("truncated"):
        print(f"  ** Results truncated at {data['row_count']} rows. Use --limit to increase.")


def fmt_csv(data: dict):
    import csv
    import io

    columns = data.get("columns", [])
    rows = data.get("rows", [])
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=columns)
    writer.writeheader()
    writer.writerows(rows)
    print(output.getvalue(), end="")


FORMATTERS = {"json": fmt_json, "table": fmt_table, "csv": fmt_csv}


def output(data: dict, fmt: str):
    FORMATTERS.get(fmt, fmt_json)(data)


# -- Subcommand: query --

def register_query(sub):
    p = sub.add_parser("query", help="Execute a read-only SQL query")
    p.add_argument("--sql", required=True, help="SQL SELECT statement to execute")
    p.add_argument("--limit", type=int, default=DEFAULT_ROW_LIMIT, help=f"Max rows (default {DEFAULT_ROW_LIMIT})")
    p.add_argument("--format", choices=["json", "table", "csv"], default="json", help="Output format")


def run_query(args):
    with MunisClient() as client:
        try:
            result = client.execute_query(args.sql, limit=args.limit)
            output(result, args.format)
        except PermissionError as e:
            print(json.dumps({"error": str(e)}))
            sys.exit(1)
        except Exception as e:
            print(json.dumps({"error": str(e)}))
            sys.exit(1)


# -- Subcommand: tables --

def register_tables(sub):
    p = sub.add_parser("tables", help="List tables and views")
    p.add_argument("--schema", default=None, help="Filter by schema name")
    p.add_argument("--filter", default=None, help="Filter table name (SQL LIKE pattern, e.g. 'GL%%')")
    p.add_argument("--format", choices=["json", "table", "csv"], default="json", help="Output format")


def run_tables(args):
    with MunisClient() as client:
        tables = client.list_tables(schema=args.schema, filter_name=args.filter)
        data = {
            "columns": ["schema", "name", "type"],
            "rows": tables,
            "row_count": len(tables),
            "truncated": False,
        }
        output(data, args.format)


# -- Subcommand: functions --

def register_functions(sub):
    p = sub.add_parser("functions", help="List reporting table-valued functions")
    p.add_argument("--schema", default=None, help="Filter by ReportingServices schema")
    p.add_argument("--format", choices=["json", "table", "csv"], default="json", help="Output format")


def run_functions(args):
    with MunisClient() as client:
        funcs = client.list_functions(schema=args.schema)
        data = {
            "columns": ["schema", "name", "return_type"],
            "rows": funcs,
            "row_count": len(funcs),
            "truncated": False,
        }
        output(data, args.format)


# -- Subcommand: describe --

def register_describe(sub):
    p = sub.add_parser("describe", help="Describe columns of a table, view, or function")
    p.add_argument("--table", default=None, help="Table or view name")
    p.add_argument("--function", default=None, help="Table-valued function name")
    p.add_argument("--schema", default="dbo", help="Schema name (default: dbo)")
    p.add_argument("--format", choices=["json", "table", "csv"], default="json", help="Output format")


def run_describe(args):
    with MunisClient() as client:
        try:
            if args.function:
                info = client.describe_function(args.function, schema=args.schema)
                fmt_json(info)
            elif args.table:
                cols = client.describe_table(args.table, schema=args.schema)
                data = {
                    "columns": ["column", "type", "max_length", "precision", "scale", "nullable", "default"],
                    "rows": cols,
                    "row_count": len(cols),
                    "truncated": False,
                }
                output(data, args.format)
            else:
                print(json.dumps({"error": "Provide either --table or --function"}))
                sys.exit(1)
        except ValueError as e:
            print(json.dumps({"error": str(e)}))
            sys.exit(1)


# -- Subcommand: report --

def register_report(sub):
    p = sub.add_parser("report", help="Run a pre-built report template")
    p.add_argument("--name", required=True, help="Report template name")
    p.add_argument("--params", default="{}", help='JSON parameters (e.g. \'{"fiscal_year":"2026"}\')')
    p.add_argument("--limit", type=int, default=DEFAULT_ROW_LIMIT, help=f"Max rows (default {DEFAULT_ROW_LIMIT})")
    p.add_argument("--format", choices=["json", "table", "csv"], default="json", help="Output format")


def run_report(args):
    from munis_reports import get_report, list_reports

    try:
        params = json.loads(args.params)
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"Invalid JSON in --params: {e}"}))
        sys.exit(1)

    report = get_report(args.name)
    if report is None:
        available = [r["name"] for r in list_reports()]
        print(json.dumps({
            "error": f"Unknown report: '{args.name}'",
            "available_reports": available,
        }))
        sys.exit(1)

    with MunisClient() as client:
        sql_template, query_params = report["build"](params)
        sql = sql_template.replace("{user}", client.user).replace("{limit}", str(args.limit))

        try:
            result = client.execute_query(sql, params=query_params if query_params else None, limit=args.limit)
            result["report"] = args.name
            result["parameters"] = params
            output(result, args.format)
        except Exception as e:
            print(json.dumps({"error": str(e)}))
            sys.exit(1)


# -- Subcommand: reports --

def register_reports(sub):
    sub.add_parser("reports", help="List available report templates")


def run_reports(args):
    from munis_reports import list_reports
    reports = list_reports()
    data = {
        "columns": ["name", "description", "parameters"],
        "rows": reports,
        "row_count": len(reports),
        "truncated": False,
    }
    output(data, "json")


# -- Main --

COMMANDS = {
    "query": run_query,
    "tables": run_tables,
    "functions": run_functions,
    "describe": run_describe,
    "report": run_report,
    "reports": run_reports,
}


def main():
    parser = argparse.ArgumentParser(
        prog="munis.py",
        description="Munis ODBC Bridge -- read-only access to Tyler Munis ERP",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    register_query(sub)
    register_tables(sub)
    register_functions(sub)
    register_describe(sub)
    register_report(sub)
    register_reports(sub)

    args = parser.parse_args()
    COMMANDS[args.command](args)


if __name__ == "__main__":
    main()
