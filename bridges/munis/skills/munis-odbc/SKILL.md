---
name: munis-odbc
description: Read-only ODBC access to the Tyler Munis ERP SQL Server database for financial reporting, budget analysis, payroll data, vendor payments, and ad-hoc queries. Connects to Tyler-hosted cloud instance via site-to-site VPN.
compatibility:
  - platform: linux
    arch: amd64
    min_version: "2026.02.21"
metadata:
  author: tendril-project
  version: "1.1.0"
  tendril-bridge: "true"
  skill_scope: bridge
  tags:
    - tyler
    - munis
    - erp
    - finance
    - budget
    - payroll
    - odbc
    - sql-server
    - reporting
credentials:
  - key: MUNIS_DB_USER
    env: MUNIS_DB_USER
    description: Per-operator SQL Server username (from Tyler Deploy > Database Info > Database User)
  - key: MUNIS_DB_PASSWORD
    env: MUNIS_DB_PASSWORD
    description: Per-operator SQL Server password
---

# Munis ODBC Bridge

Read-only ODBC access to the Tyler Technologies Munis ERP SQL Server database. Connects to the Tyler-hosted cloud instance over a site-to-site VPN using Microsoft ODBC Driver 18 with TLS encryption.

## Tyler Munis Data Architecture

**This is critical context for writing queries against Munis.**

Tyler Munis does **not** expose reporting data through direct table access in the `dbo` schema. Instead, data is accessed through **table-valued functions** in dedicated `*ReportingServices` schemas. Almost every function requires a `@UserName` parameter (the SQL login name) that controls row-level access based on the operator's Munis application user profile.

### How to query Munis data

```sql
-- CORRECT: Use the reporting services function with @UserName
SELECT TOP 100 * FROM GeneralLedgerReportingServices.Detail('your_sql_login')

-- WRONG: Direct dbo table access returns 0 rows for reporting accounts
SELECT * FROM dbo.gl_detail  -- Returns 0 rows
```

The `@UserName` parameter is the SQL login (i.e. the value of `MUNIS_DB_USER`). This is automatically injected by the `report` subcommand via the `{user}` placeholder.

### SQL Account Requirements

The SQL login must be a member of the **`MunisReportDesigners`** database role. This role grants:
- `SELECT` and `EXECUTE` on all `*ReportingServices` schemas
- Access to the reporting table-valued functions

The role alone is not sufficient -- the corresponding Munis application user profile must also have module access configured in Tyler's admin console. A login with the SQL role but no application modules will authenticate successfully but return 0 rows from all functions.

### Available Reporting Schemas

| Schema | Description | Key Functions |
|--------|-------------|---------------|
| `GeneralLedgerReportingServices` | GL accounts, journals, budgets | `Detail`, `Master`, `Budget`, `MasterBalance`, `History`, `FundData`, `Object` |
| `PayrollReportingServices` | Employee data, checks, period summaries | `EmployeeMaster`, `Checks`, `PeriodSummary`, `EarnHistory`, `BasePay`, `JobClass` |
| `AccountsPayableReportingServices` | Vendors, invoices, POs | `AccountsPayableVendors`, `AccountsPayableInvoices`, `PurchaseOrders` |
| `HumanResourcesReportingServices` | HR actions, deductions, applicants | `ActionHistory`, `EmployeeDeductions`, `HumanResourcesApplicantData` |
| `FixedAssetReportingServices` | Capital asset inventory | `FixedAssetMaster`, `FixedAssetCodes`, `ScheduleK` |
| `TaxReportingServices` | Tax parcels, owners, values | `TaxParcelMaster`, `TaxOwners`, `TaxValues`, `TaxCharges` |
| `PurchasingReportingServices` | Bids, tabulations, item files | `BidDetailsUDF`, `BidVendorsUDF`, `ItemFileUsage` |
| `AccountsReceivableReportingServices` | AR bills, customers, receipts | `AccountsReceivableAllBills`, `AccountsReceivableCustomers` |
| `UtilityBillingReportingServices` | Utility billing accounts and charges | `UtilityBillingAccountMaster`, `UtilityBillingCharges` |
| `WorkOrdersReportingServices` | Work order management | `WorkOrdersMaster`, `WorkOrdersDetails`, `WorkOrdersAssets` |
| `PermitsReportingServices` | Permit applications and inspections | `PermitsApplicationMaster`, `PermitsApplicationInspection` |
| `EmployeeExpenseReportingServices` | Employee expense claims | `EmployeeExpenseClaimMaster` |
| `CashFlowReportingServices` | Cash flow tracking | `CashFlowMaster` |
| `SystemReportingServices` | System codes, departments | `SystemDepartmentCodes`, `SystemMiscellaneousCodes` |
| `PayrollAuditReportingServices` | Payroll audit trail (592 audit views) | Various `*AuditDetail` / `*AuditHeader` views |

### Function Parameters

Most functions take only `@UserName`. Notable exceptions:
- `AccountsPayableInvoices(@UserName, @IsPosted)` -- requires a `smallint` posted flag

Use the `describe` command to inspect any function's parameters and return columns:

```bash
python3 /opt/bridge/data/tools/munis.py describe --function Detail --schema GeneralLedgerReportingServices
```

## Authentication

- **Type:** SQL Server authentication via ODBC Driver 18
- **Connection:** Site-to-site VPN to Tyler cloud, TLS encrypted, `TrustServerCertificate=yes` (Tyler-hosted instances use certificates not in the public CA chain)
- **Shared credentials:** `MUNIS_DB_HOST`, `MUNIS_DB_NAME` (set in container environment)
- **Per-operator credentials:** `MUNIS_DB_USER`, `MUNIS_DB_PASSWORD` (injected by Tendril Root from credential vault at runtime)

### Finding your connection details in Tyler Deploy

The shared credential values (`MUNIS_DB_HOST` and `MUNIS_DB_NAME`) are found in the Tyler Deploy portal:

1. Log in to [Tyler Deploy](https://tylerdeploy.com)
2. Navigate to **Site Report**
3. Select the desired **Environment** (Prod, Test, or Train)
4. Expand the **Munis ERP** section
5. Under **Database Info**:
   - **SQL Instance** -- this is the server prefix. The full hostname for `MUNIS_DB_HOST` is `<SQL Instance>.tylerhost.net`
   - **Database User** (listed below the SQL Instance) -- this is the value for `MUNIS_DB_NAME`

For example, if Tyler Deploy shows SQL Instance `abcdefgh01cs02` and Database User `mun1234prod`, then:
- `MUNIS_DB_HOST` = `abcdefgh01cs02.tylerhost.net`
- `MUNIS_DB_NAME` = `mun1234prod`

## Tools

| Script | Location | Purpose |
|--------|----------|---------|
| `munis_client.py` | `/opt/bridge/data/tools/` | Core ODBC client with read-only enforcement, type serialization, schema/function inspection |
| `munis_check.py` | `/opt/bridge/data/tools/` | Health check: validates ODBC driver, env vars, TCP connectivity, DB auth |
| `munis.py` | `/opt/bridge/data/tools/` | Unified CLI with subcommands for queries, schema browsing, function inspection, and reports |
| `munis_reports.py` | `/opt/bridge/data/tools/` | Pre-built report templates using Tyler Reporting Services functions |

## CLI: python3 /opt/bridge/data/tools/munis.py <command> [options]

### Commands

#### query -- Execute ad-hoc SQL

Run a read-only SELECT query against the Munis database. For reporting data, queries must use the `Schema.Function(@UserName)` pattern.

```bash
# GL journal entries for fiscal year 2026 (replace MUNIS_DB_USER with actual login)
python3 /opt/bridge/data/tools/munis.py query \
  --sql "SELECT TOP 50 a_fund_seg1, a_org, a_object, j_debit_amount, j_credit_amount, j_effective_date FROM GeneralLedgerReportingServices.Detail('$MUNIS_DB_USER') WHERE j_jnl_year_period / 100 = 2026" \
  --format table

# Search vendors by name
python3 /opt/bridge/data/tools/munis.py query \
  --sql "SELECT a_vendor_number, a_vendor_name, v_vend_city FROM AccountsPayableReportingServices.AccountsPayableVendors('$MUNIS_DB_USER') WHERE a_vendor_name LIKE '%DUKE%'" \
  --format table

# Active employee count by department
python3 /opt/bridge/data/tools/munis.py query \
  --sql "SELECT a_org_primary AS dept, COUNT(*) AS headcount FROM PayrollReportingServices.EmployeeMaster('$MUNIS_DB_USER') WHERE e_activity_status = 'A' GROUP BY a_org_primary ORDER BY headcount DESC" \
  --limit 20 --format table
```

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `--sql` | Yes | -- | SQL SELECT statement (only SELECT and WITH/CTE allowed) |
| `--limit` | No | 1000 | Maximum rows to return |
| `--format` | No | json | Output format: `json`, `table`, or `csv` |

**Important:** Replace the username in the function call with the operator's actual `MUNIS_DB_USER` value.

#### functions -- List reporting table-valued functions

Browse available Tyler Reporting Services functions. This is the primary way to discover what data is available.

```bash
# List all reporting functions across all schemas
python3 /opt/bridge/data/tools/munis.py functions --format table

# List functions in a specific schema
python3 /opt/bridge/data/tools/munis.py functions --schema PayrollReportingServices --format table
```

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `--schema` | No | all ReportingServices | Filter to a single schema |
| `--format` | No | json | Output format |

#### tables -- List tables and views

```bash
python3 /opt/bridge/data/tools/munis.py tables --schema PayrollAuditReportingServices --format table
```

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `--schema` | No | all | Filter by schema name |
| `--filter` | No | all | SQL LIKE pattern for table name |
| `--format` | No | json | Output format |

#### describe -- Describe a table, view, or function

Use `--function` to inspect a reporting function's parameters and return columns. Use `--table` for tables/views.

```bash
# Inspect a reporting function (shows parameters AND return columns)
python3 /opt/bridge/data/tools/munis.py describe --function Detail --schema GeneralLedgerReportingServices

# Inspect a table or view
python3 /opt/bridge/data/tools/munis.py describe --table JournalLineAmounts --schema GeneralLedgerReportingServices --format table
```

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `--table` | No* | -- | Table or view name |
| `--function` | No* | -- | Table-valued function name |
| `--schema` | No | dbo | Schema name |
| `--format` | No | json | Output format |

*Provide either `--table` or `--function`, not both.

#### report -- Run a pre-built report

Pre-built reports handle the `@UserName` injection and column selection automatically. The `{user}` placeholder is replaced with the operator's SQL login at runtime.

```bash
# GL journal detail for fiscal year 2026
python3 /opt/bridge/data/tools/munis.py report --name gl_detail --params '{"fiscal_year":"2026"}' --format table

# Budget vs actual comparison
python3 /opt/bridge/data/tools/munis.py report --name budget_vs_actual --params '{"fiscal_year":"2026"}' --limit 500 --format table

# Active employees
python3 /opt/bridge/data/tools/munis.py report --name employee_list --format table

# Vendor search
python3 /opt/bridge/data/tools/munis.py report --name vendor_list --params '{"name":"DUKE"}' --format table

# Recent payroll checks
python3 /opt/bridge/data/tools/munis.py report --name payroll_checks --limit 20 --format table
```

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `--name` | Yes | -- | Report template name |
| `--params` | No | {} | JSON parameters for the report |
| `--limit` | No | 1000 | Maximum rows |
| `--format` | No | json | Output format |

#### reports -- List available report templates

```bash
python3 /opt/bridge/data/tools/munis.py reports
```

### Available Reports

| Report Name | Description | Parameters | Source Function |
|------------|-------------|------------|-----------------|
| `gl_detail` | GL journal detail (debits/credits) | `fiscal_year`, `fund` (optional) | `GeneralLedgerReportingServices.Detail` |
| `gl_budget` | GL budget amounts (projected) | `fiscal_year` (optional) | `GeneralLedgerReportingServices.Budget` |
| `budget_vs_actual` | Budget vs. actual expenditure | `fiscal_year` (default: 2026) | `Budget` + `Detail` join |
| `gl_master` | Chart of accounts | `fund` (optional) | `GeneralLedgerReportingServices.Master` |
| `vendor_list` | AP vendor directory | `name` (optional filter) | `AccountsPayableReportingServices.AccountsPayableVendors` |
| `purchase_orders` | Purchase orders | (none) | `AccountsPayableReportingServices.PurchaseOrders` |
| `employee_list` | Employee roster | `status` (default: A) | `PayrollReportingServices.EmployeeMaster` |
| `payroll_summary` | Payroll totals by dept/period | `period` (optional) | `PayrollReportingServices.PeriodSummary` |
| `payroll_checks` | Payroll check register | (none) | `PayrollReportingServices.Checks` |
| `fixed_assets` | Fixed asset inventory | (none) | `FixedAssetReportingServices.FixedAssetMaster` |
| `hr_actions` | HR action history | (none) | `HumanResourcesReportingServices.ActionHistory` |

## Key Column Reference

### GeneralLedgerReportingServices.Detail

| Column | Description |
|--------|-------------|
| `a_fund_seg1` | Fund code (e.g. `11`) |
| `a_org` | Organization/department code |
| `a_object` | Object/account code |
| `j_jnl_year_period` | Fiscal year and period as integer (e.g. `202608` = FY2026 period 08) |
| `j_debit_amount` | Debit amount |
| `j_credit_amount` | Credit amount |
| `j_effective_date` | Transaction effective date |
| `j_ref1_vendor` | Vendor reference |
| `j_ref2_po_no` | PO number reference |
| `j_ref3_invoice_no` | Invoice number reference |
| `j_ref4_jnl_desc` | Journal description |

### PayrollReportingServices.EmployeeMaster

| Column | Description |
|--------|-------------|
| `a_employee_number` | Employee ID |
| `a_name_last`, `a_name_first` | Employee name |
| `a_org_primary` | Primary department code |
| `a_job_class_desc` | Job title |
| `e_hire_date` | Hire date |
| `e_activity_status` | Status (`A` = active, `I` = inactive, `T` = terminated) |
| `e_email` | Email address |

### PayrollReportingServices.Checks

| Column | Description |
|--------|-------------|
| `a_employee_number` | Employee ID |
| `a_check` | Check number |
| `a_check_date` | Check date |
| `ck_gross_pay` | Gross pay amount |
| `ck_net_pay` | Net pay amount |
| `a_org` | Department code |

### AccountsPayableReportingServices.AccountsPayableVendors

| Column | Description |
|--------|-------------|
| `a_vendor_number` | Vendor ID |
| `a_vendor_name` | Vendor name |
| `v_vend_address1` | Street address |
| `v_vend_city`, `v_vend_state`, `v_vend_zip` | City, state, ZIP |

## Security

- **Read-only enforcement:** Connection string uses `ApplicationIntent=ReadOnly`; application layer rejects INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, TRUNCATE, EXEC, EXECUTE, MERGE, GRANT, REVOKE, DENY statements
- **Tyler row-level security:** The `@UserName` parameter in every reporting function enforces data access based on the operator's Munis application profile
- **TLS encryption:** ODBC Driver 18 enforces TLS; `TrustServerCertificate=yes` is required for Tyler-hosted instances
- **Row limits:** Default 1000-row cap prevents accidental full-table dumps
- **Per-operator attribution:** Each operator authenticates with their own SQL credentials from the Tendril vault; all queries are attributed to the individual user

## Troubleshooting

```bash
# Full health check (requires per-operator creds)
python3 /opt/bridge/data/tools/munis_check.py

# Quick infrastructure check (no auth needed)
python3 /opt/bridge/data/tools/munis_check.py --quick

# Test ODBC client directly
python3 /opt/bridge/data/tools/munis_client.py test
```

### Common Issues

- **"ODBC Driver 18 not found"** -- The Microsoft ODBC driver is not installed in the container. Rebuild the image.
- **"Connection timed out"** -- The Munis SQL Server is not reachable. Check VPN tunnel status and verify the container can route to the Tyler cloud network.
- **"Login failed"** -- Per-operator credentials are incorrect or not provisioned in the Tendril vault.
- **"Write operations are not permitted"** -- Only SELECT and WITH (CTE) queries are allowed. The bridge is read-only by design.
- **"SSL Provider: certificate verify failed"** -- The connection string must include `TrustServerCertificate=yes` for Tyler-hosted instances.
- **Queries return 0 rows** -- Verify the SQL login has both the `MunisReportDesigners` database role AND Munis application module access configured. The SQL role alone is not sufficient. Also ensure queries use the `Schema.Function(@UserName)` pattern, not direct `dbo` table access.
- **"An insufficient number of arguments"** -- The table-valued function requires parameters. Use `describe --function NAME --schema SCHEMA` to see required parameters. Most functions need only `@UserName`, but some (like `AccountsPayableInvoices`) require additional arguments.
