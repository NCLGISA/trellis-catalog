"""
Verizon MyBusiness Bridge -- Billing

Retrieve billing account summaries, invoice amounts, and payment status.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from verizon_client import VerizonClient, require_credentials


def main():
    if len(sys.argv) < 2:
        print("Usage: billing_check.py <command> [options]")
        print("Commands: summary, account <account_number>, invoices")
        sys.exit(1)

    require_credentials()
    cmd = sys.argv[1]
    client = VerizonClient()

    if cmd in ("summary", "invoices"):
        billing = client.get_billing_accounts()
        accounts = billing.get("accountInfo", [])

        if not accounts:
            print("No billing accounts found")
            sys.exit(1)

        total_due = 0
        print(f"{'Account':<20} {'Name':<20} {'Balance':>12} {'Due Date':<15} {'AutoPay':<8} {'Paperless'}")
        print("─" * 90)
        for acct in accounts:
            balance = acct.get("totalBalanceDue", 0)
            total_due += balance
            print(f"{acct['accountNumber']:<20} {acct.get('accountName', ''):<20} "
                  f"${balance:>10,.2f} {acct.get('paymentDueDate', ''):<15} "
                  f"{'Yes' if acct.get('autoPayIndicator') == 'Y' else 'No':<8} "
                  f"{'Yes' if acct.get('paperlessIndicator') == 'Y' else 'No'}")

        print(f"\nTotal balance due: ${total_due:,.2f}")
        print(f"Accounts: {len(accounts)}")

        if cmd == "invoices":
            print(f"\nInvoice Details:")
            for acct in accounts:
                print(f"\n  Account: {acct['accountNumber']} ({acct.get('accountName', '')})")
                print(f"    Invoice #: {acct.get('invoiceNumber', '?')}")
                print(f"    Invoice date: {acct.get('invoiceDate', '?')}")
                print(f"    Invoice amount: ${float(acct.get('invoiceAmount', 0)):,.2f}")
                print(f"    Balance due: ${acct.get('totalBalanceDue', 0):,.2f}")
                print(f"    Payment due: {acct.get('paymentDueDate', '?')}")
                print(f"    Past due: {'Yes' if acct.get('pastDueFlag') == 'Y' else 'No'}")
                print(f"    Bill cycle: {acct.get('billCycleNumber', '?')}")
                print(f"    Net terms: {acct.get('netPaymentTermDays', '?')} days")

    elif cmd == "account":
        if len(sys.argv) < 3:
            print("Usage: billing_check.py account <account_number>")
            sys.exit(1)
        target = sys.argv[2]

        billing = client.get_billing_accounts()
        accounts = billing.get("accountInfo", [])
        acct = next((a for a in accounts if a["accountNumber"] == target), None)

        if not acct:
            print(f"Account {target} not found")
            sys.exit(1)

        for key, value in sorted(acct.items()):
            print(f"  {key}: {value}")

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
