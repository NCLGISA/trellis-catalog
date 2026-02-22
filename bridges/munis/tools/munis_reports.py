"""
Munis Pre-Built Report Templates -- Tyler Reporting Services Functions

Parameterized SQL report templates that query Tyler Munis Reporting
Services table-valued functions. Each function lives in a dedicated
*ReportingServices schema and requires @UserName as the first parameter
for row-level security filtering.

The {user} placeholder is replaced at runtime with the operator's SQL
login name (MUNIS_DB_USER). The {limit} placeholder is replaced with
the row limit.
"""


def _build_gl_detail(params):
    fiscal_year = params.get("fiscal_year")
    fund = params.get("fund")
    sql = """
        SELECT TOP {limit}
            d.a_fund_seg1 AS fund, d.a_org AS org_code, d.a_object AS object_code,
            d.a_project AS project, d.j_jnl_year_period AS year_period,
            d.a_journal_number AS journal_number, d.j_debit_amount AS debit,
            d.j_credit_amount AS credit, d.j_ref1_vendor AS vendor_ref,
            d.j_ref4_jnl_desc AS description, d.j_effective_date AS effective_date
        FROM GeneralLedgerReportingServices.Detail('{user}') d
        WHERE 1=1
    """
    if fiscal_year:
        sql += f" AND d.j_jnl_year_period / 100 = {int(fiscal_year)}"
    if fund:
        sql += f" AND d.a_fund_seg1 = '{fund}'"
    sql += " ORDER BY d.j_effective_date DESC"
    return sql, ()


def _build_gl_budget(params):
    sql = """
        SELECT TOP {limit}
            b.a_org AS org_code, b.a_object AS object_code,
            b.bm_fsc_yr AS fiscal_year, b.bd_account_type AS account_type,
            b.bd_bud_cy_projctd AS projected_budget
        FROM GeneralLedgerReportingServices.Budget('{user}') b WHERE 1=1
    """
    fiscal_year = params.get("fiscal_year")
    if fiscal_year:
        sql += f" AND b.bm_fsc_yr = {int(fiscal_year)}"
    sql += " ORDER BY b.a_org, b.a_object"
    return sql, ()


def _build_budget_vs_actual(params):
    fy = str(int(params.get("fiscal_year", "2026")))
    sql = f"""
        SELECT TOP {{limit}}
            b.a_org AS org_code, b.a_object AS object_code,
            b.bd_account_type AS account_type, b.bd_bud_cy_projctd AS budget_amount,
            ISNULL(a.actual_amt, 0) AS actual_amount,
            b.bd_bud_cy_projctd - ISNULL(a.actual_amt, 0) AS remaining
        FROM GeneralLedgerReportingServices.Budget('{{user}}') b
        LEFT JOIN (
            SELECT a_org, a_object,
                   SUM(j_debit_amount) - SUM(j_credit_amount) AS actual_amt
            FROM GeneralLedgerReportingServices.Detail('{{user}}')
            WHERE j_jnl_year_period / 100 = {fy}
            GROUP BY a_org, a_object
        ) a ON b.a_org = a.a_org AND b.a_object = a.a_object
        WHERE b.bm_fsc_yr = {fy} AND b.bd_account_type = 'E'
        ORDER BY b.a_org, b.a_object
    """
    return sql, ()


def _build_gl_master(params):
    fund = params.get("fund")
    sql = """
        SELECT TOP {limit}
            m.a_account_type AS account_type, m.a_fund_seg1 AS fund,
            m.a_org AS org_code, m.a_object AS object_code,
            m.a_project AS project, m.a_account_desc AS description
        FROM GeneralLedgerReportingServices.Master('{user}') m WHERE 1=1
    """
    if fund:
        sql += f" AND m.a_fund_seg1 = '{fund}'"
    sql += " ORDER BY m.a_fund_seg1, m.a_org, m.a_object"
    return sql, ()


def _build_vendor_list(params):
    name_filter = params.get("name")
    sql = """
        SELECT TOP {limit}
            v.a_vendor_number AS vendor_number, v.a_vendor_name AS vendor_name,
            v.v_vend_address1 AS address1, v.v_vend_city AS city,
            v.v_vend_state AS state, v.v_vend_zip AS zip
        FROM AccountsPayableReportingServices.AccountsPayableVendors('{user}') v WHERE 1=1
    """
    if name_filter:
        sql += f" AND v.a_vendor_name LIKE '%{name_filter}%'"
    sql += " ORDER BY v.a_vendor_name"
    return sql, ()


def _build_purchase_orders(params):
    sql = (
        "SELECT TOP {limit} po.* "
        "FROM AccountsPayableReportingServices.PurchaseOrders('{user}') po "
        "ORDER BY 1 DESC"
    )
    return sql, ()


def _build_employee_list(params):
    status = params.get("status", "A")
    sql = f"""
        SELECT TOP {{limit}}
            e.a_employee_number AS employee_number, e.a_name_last AS last_name,
            e.a_name_first AS first_name, e.a_org_primary AS org_code,
            e.a_job_class_desc AS job_title, e.e_hire_date AS hire_date,
            e.e_activity_status AS status
        FROM PayrollReportingServices.EmployeeMaster('{{user}}') e
        WHERE e.e_activity_status = '{status}'
        ORDER BY e.a_name_last, e.a_name_first
    """
    return sql, ()


def _build_payroll_summary(params):
    period = params.get("period")
    sql = """
        SELECT TOP {limit}
            ps.a_org AS org_code, ps.or_description AS department,
            ps.ps_period AS pay_period,
            COUNT(DISTINCT ps.a_employee_number) AS employee_count,
            SUM(ps.ps_cur_earnings) AS total_gross,
            SUM(ps.ps_cur_net) AS total_net,
            SUM(ps.ps_cur_deduction) AS total_deductions
        FROM PayrollReportingServices.PeriodSummary('{user}') ps
        WHERE ps.ps_void != 'Y'
    """
    if period:
        sql += f" AND ps.ps_period = '{period}'"
    sql += (
        " GROUP BY ps.a_org, ps.or_description, ps.ps_period"
        " ORDER BY ps.ps_period DESC, ps.a_org"
    )
    return sql, ()


def _build_payroll_checks(params):
    sql = """
        SELECT TOP {limit}
            c.a_employee_number AS employee_number,
            c.a_check AS check_number, c.a_check_date AS check_date,
            c.ck_gross_pay AS gross, c.ck_net_pay AS net,
            c.a_org AS org_code, c.a_warrant AS warrant
        FROM PayrollReportingServices.Checks('{user}') c
        ORDER BY c.a_check_date DESC, c.a_employee_number
    """
    return sql, ()


def _build_fixed_assets(params):
    sql = (
        "SELECT TOP {limit} fa.* "
        "FROM FixedAssetReportingServices.FixedAssetMaster('{user}') fa "
        "ORDER BY 1"
    )
    return sql, ()


def _build_hr_actions(params):
    sql = (
        "SELECT TOP {limit} h.* "
        "FROM HumanResourcesReportingServices.ActionHistory('{user}') h "
        "ORDER BY 1 DESC"
    )
    return sql, ()


# -- Report Registry --

REPORTS = {
    "gl_detail": {
        "name": "gl_detail",
        "description": "General Ledger journal detail (debits/credits by account)",
        "parameters": "fiscal_year (optional), fund (optional)",
        "build": _build_gl_detail,
    },
    "gl_budget": {
        "name": "gl_budget",
        "description": "General Ledger budget amounts (projected)",
        "parameters": "fiscal_year (optional)",
        "build": _build_gl_budget,
    },
    "budget_vs_actual": {
        "name": "budget_vs_actual",
        "description": "Budget vs. actual expenditure comparison",
        "parameters": "fiscal_year (default: 2026)",
        "build": _build_budget_vs_actual,
    },
    "gl_master": {
        "name": "gl_master",
        "description": "Chart of accounts (GL master account list)",
        "parameters": "fund (optional)",
        "build": _build_gl_master,
    },
    "vendor_list": {
        "name": "vendor_list",
        "description": "Accounts Payable vendor directory",
        "parameters": "name (optional substring filter)",
        "build": _build_vendor_list,
    },
    "purchase_orders": {
        "name": "purchase_orders",
        "description": "Purchase orders from Accounts Payable",
        "parameters": "(none)",
        "build": _build_purchase_orders,
    },
    "employee_list": {
        "name": "employee_list",
        "description": "Employee roster with job title and hire date",
        "parameters": "status (default: A for active)",
        "build": _build_employee_list,
    },
    "payroll_summary": {
        "name": "payroll_summary",
        "description": "Payroll totals by department and pay period",
        "parameters": "period (optional)",
        "build": _build_payroll_summary,
    },
    "payroll_checks": {
        "name": "payroll_checks",
        "description": "Payroll check register (most recent first)",
        "parameters": "(none)",
        "build": _build_payroll_checks,
    },
    "fixed_assets": {
        "name": "fixed_assets",
        "description": "Fixed asset inventory",
        "parameters": "(none)",
        "build": _build_fixed_assets,
    },
    "hr_actions": {
        "name": "hr_actions",
        "description": "Human Resources action history",
        "parameters": "(none)",
        "build": _build_hr_actions,
    },
}


def get_report(name):
    return REPORTS.get(name)


def list_reports():
    return [
        {"name": r["name"], "description": r["description"], "parameters": r["parameters"]}
        for r in REPORTS.values()
    ]
