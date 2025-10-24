"""
Invoice Generation Module

Generates CSV invoices matching the integodash format for compatibility.
Each invoice contains itemized charges for users, assets, tickets, and custom items.
"""

import io
import csv
from datetime import datetime, timedelta
import calendar
from app.codex_client import get_billing_data_from_codex
from app.billing_engine import get_billing_data_for_client


def generate_invoice_number(account_number, year, month):
    """
    Generate invoice number in format: ACCOUNT-YYYYMM
    Example: 620547-202510
    """
    return f"{account_number}-{year}{month:02d}"


def generate_invoice_csv(account_number, year, month):
    """
    Generate a CSV invoice for a specific company and billing period.

    Returns:
        tuple: (csv_string, company_name, invoice_number) or (None, None, None) if failed
    """
    # Fetch data from Codex
    codex_data = get_billing_data_from_codex(account_number)
    if not codex_data:
        return None, None, None

    # Calculate billing
    billing_data = get_billing_data_for_client(
        codex_data['company'],
        codex_data['assets'],
        codex_data['users'],
        year,
        month,
        codex_data.get('tickets', [])
    )

    if not billing_data:
        return None, None, None

    company_name = codex_data['company'].get('name', 'Unknown')
    invoice_number = generate_invoice_number(account_number, year, month)

    # Calculate invoice date (last day of billing month)
    _, last_day = calendar.monthrange(year, month)
    invoice_date = datetime(year, month, last_day).strftime('%Y-%m-%d')

    # Calculate due date (30 days after invoice date)
    invoice_dt = datetime(year, month, last_day)
    due_date = (invoice_dt + timedelta(days=30)).strftime('%Y-%m-%d')

    # Build CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)

    # Header row
    writer.writerow([
        'InvoiceNo',
        'Customer',
        'InvoiceDate',
        'DueDate',
        'Item(Product/Service)',
        'Description',
        'Qty',
        'Rate',
        'Amount'
    ])

    receipt = billing_data['receipt_data']

    # Write user charges
    for user in receipt['billed_users']:
        billing_type = user['type']
        cost = user['cost']

        # Only include if there's a cost
        if cost > 0:
            writer.writerow([
                invoice_number,
                company_name,
                invoice_date,
                due_date,
                'Managed Services',
                f"User: {user['name']} ({billing_type})",
                1,
                f"{cost:.2f}",
                f"{cost:.2f}"
            ])

    # Write asset charges
    for asset in receipt['billed_assets']:
        billing_type = asset['type']
        cost = asset['cost']

        # Only include if there's a cost
        if cost > 0:
            writer.writerow([
                invoice_number,
                company_name,
                invoice_date,
                due_date,
                'Managed Services',
                f"Asset: {asset['name']} ({billing_type})",
                1,
                f"{cost:.2f}",
                f"{cost:.2f}"
            ])

    # Write backup charges if any
    if receipt.get('backup_charge', 0) > 0:
        backup_details = []

        if receipt.get('backup_base_workstation', 0) > 0:
            backup_details.append(
                f"Workstation Backup Base: ${receipt['backup_base_workstation']:.2f}"
            )

        if receipt.get('backup_base_server', 0) > 0:
            backup_details.append(
                f"Server Backup Base: ${receipt['backup_base_server']:.2f}"
            )

        if receipt.get('overage_tb', 0) > 0:
            backup_details.append(
                f"Overage: {receipt['overage_tb']:.2f} TB @ ${receipt['overage_charge']:.2f}"
            )

        backup_desc = "Backup Services - " + ", ".join(backup_details)

        writer.writerow([
            invoice_number,
            company_name,
            invoice_date,
            due_date,
            'Backup Services',
            backup_desc,
            1,
            f"{receipt['backup_charge']:.2f}",
            f"{receipt['backup_charge']:.2f}"
        ])

    # Write ticket/hourly charges if any
    if receipt.get('billable_hours', 0) > 0:
        hours = receipt['billable_hours']
        per_hour = receipt['ticket_charge'] / hours if hours > 0 else 0

        writer.writerow([
            invoice_number,
            company_name,
            invoice_date,
            due_date,
            'Hourly Labor',
            f"Billable Hours ({hours:.2f} hrs)",
            f"{hours:.2f}",
            f"{per_hour:.2f}",
            f"{receipt['ticket_charge']:.2f}"
        ])

    # Write custom line items
    for item in receipt['billed_line_items']:
        cost = item['cost']
        item_type = item['type']  # Recurring, One-Off, Yearly

        writer.writerow([
            invoice_number,
            company_name,
            invoice_date,
            due_date,
            'Custom Charge',
            f"{item['name']} ({item_type})",
            1,
            f"{cost:.2f}",
            f"{cost:.2f}"
        ])

    csv_content = output.getvalue()
    output.close()

    return csv_content, company_name, invoice_number


def generate_bulk_invoices_zip(year, month):
    """
    Generate invoices for ALL companies for a specific billing period.
    Returns a ZIP file containing individual CSV files.

    Returns:
        tuple: (zip_bytes, filename) or (None, None) if failed
    """
    from app.codex_client import get_all_companies
    import zipfile

    companies = get_all_companies()
    if not companies:
        return None, None

    # Create ZIP in memory
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        generated_count = 0

        for company in companies:
            account_number = company.get('account_number')
            if not account_number:
                continue

            # Generate CSV for this company
            csv_content, company_name, invoice_number = generate_invoice_csv(
                account_number, year, month
            )

            if csv_content:
                # Sanitize company name for filename
                safe_name = "".join(
                    c for c in company_name if c.isalnum() or c in (' ', '_', '-')
                ).strip().replace(' ', '_')

                filename = f"{safe_name}_{year}-{month:02d}.csv"
                zip_file.writestr(filename, csv_content)
                generated_count += 1

        if generated_count == 0:
            return None, None

    zip_buffer.seek(0)
    zip_filename = f"invoices_{year}-{month:02d}.zip"

    return zip_buffer.getvalue(), zip_filename


def get_invoice_summary(account_number, year, month):
    """
    Get a summary of an invoice without generating the full CSV.
    Useful for preview/display purposes.

    Returns:
        dict: Invoice summary with totals and line counts
    """
    codex_data = get_billing_data_from_codex(account_number)
    if not codex_data:
        return None

    billing_data = get_billing_data_for_client(
        codex_data['company'],
        codex_data['assets'],
        codex_data['users'],
        year,
        month,
        codex_data.get('tickets', [])
    )

    if not billing_data:
        return None

    receipt = billing_data['receipt_data']

    return {
        'invoice_number': generate_invoice_number(account_number, year, month),
        'company_name': codex_data['company'].get('name'),
        'total_amount': receipt['total'],
        'user_count': len([u for u in receipt['billed_users'] if u['cost'] > 0]),
        'asset_count': len([a for a in receipt['billed_assets'] if a['cost'] > 0]),
        'line_item_count': len(receipt['billed_line_items']),
        'has_backup_charges': receipt.get('backup_charge', 0) > 0,
        'has_hourly_charges': receipt.get('billable_hours', 0) > 0,
        'total_lines': (
            len([u for u in receipt['billed_users'] if u['cost'] > 0]) +
            len([a for a in receipt['billed_assets'] if a['cost'] > 0]) +
            len(receipt['billed_line_items']) +
            (1 if receipt.get('backup_charge', 0) > 0 else 0) +
            (1 if receipt.get('billable_hours', 0) > 0 else 0)
        )
    }
