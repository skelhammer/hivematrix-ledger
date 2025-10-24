"""
Archive Integration for Ledger

This module handles sending billing snapshots to the Archive service.
"""

from app.service_client import call_service
from app.codex_client import get_billing_data_from_codex
from app.billing_engine import get_billing_data_for_client
from app.invoice_generator import generate_invoice_csv, generate_invoice_number
from datetime import datetime, timedelta
import calendar
import json


def create_snapshot_payload(account_number, year, month, user_email=None, notes=None):
    """
    Generate a complete snapshot payload for Archive.

    Args:
        account_number: Company account number
        year: Billing year
        month: Billing month
        user_email: Who's creating this snapshot (optional)
        notes: Optional notes about this snapshot

    Returns:
        dict: Complete snapshot payload ready for Archive API
    """
    # Get billing data from Codex
    codex_data = get_billing_data_from_codex(account_number)
    if not codex_data:
        return None

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
        return None

    # Generate CSV invoice
    csv_content, company_name, invoice_number = generate_invoice_csv(account_number, year, month)
    if not csv_content:
        return None

    # Calculate dates
    _, last_day = calendar.monthrange(year, month)
    invoice_date = datetime(year, month, last_day).strftime('%Y-%m-%d')
    due_date = (datetime(year, month, last_day) + timedelta(days=30)).strftime('%Y-%m-%d')

    # Extract receipt data
    receipt = billing_data['receipt_data']
    company = billing_data['client']

    # Build line items array
    line_items = []

    # Add user line items
    for user in receipt['billed_users']:
        if user['cost'] > 0:
            line_items.append({
                'line_type': 'user',
                'item_name': user['name'],
                'description': f"User: {user['name']} ({user['type']})",
                'quantity': 1.0,
                'rate': user['cost'],
                'amount': user['cost']
            })

    # Add asset line items
    for asset in receipt['billed_assets']:
        if asset['cost'] > 0:
            line_items.append({
                'line_type': 'asset',
                'item_name': asset['name'],
                'description': f"Asset: {asset['name']} ({asset['type']})",
                'quantity': 1.0,
                'rate': asset['cost'],
                'amount': asset['cost']
            })

    # Add backup charges
    if receipt.get('backup_charge', 0) > 0:
        line_items.append({
            'line_type': 'backup',
            'item_name': 'Backup Services',
            'description': f"Backup charges (base + {receipt.get('overage_tb', 0):.2f} TB overage)",
            'quantity': 1.0,
            'rate': receipt['backup_charge'],
            'amount': receipt['backup_charge']
        })

    # Add ticket charges
    if receipt.get('billable_hours', 0) > 0:
        hours = receipt['billable_hours']
        per_hour = receipt['ticket_charge'] / hours if hours > 0 else 0
        line_items.append({
            'line_type': 'ticket',
            'item_name': 'Billable Hours',
            'description': f"Billable Hours ({hours:.2f} hrs)",
            'quantity': hours,
            'rate': per_hour,
            'amount': receipt['ticket_charge']
        })

    # Add custom line items
    for item in receipt['billed_line_items']:
        line_items.append({
            'line_type': 'custom',
            'item_name': item['name'],
            'description': f"{item['name']} ({item['type']})",
            'quantity': 1.0,
            'rate': item['cost'],
            'amount': item['cost']
        })

    # Build complete payload
    payload = {
        'company_account_number': account_number,
        'company_name': company_name,
        'invoice_number': invoice_number,
        'billing_year': year,
        'billing_month': month,
        'invoice_date': invoice_date,
        'due_date': due_date,
        'billing_plan': company.get('billing_plan'),
        'contract_term': company.get('contract_term_length'),
        'support_level': billing_data.get('support_level_display'),
        'total_amount': float(receipt['total']),
        'total_user_charges': float(receipt['total_user_charges']),
        'total_asset_charges': float(receipt['total_asset_charges']),
        'total_backup_charges': float(receipt.get('backup_charge', 0)),
        'total_ticket_charges': float(receipt.get('ticket_charge', 0)),
        'total_line_item_charges': float(receipt.get('total_line_item_charges', 0)),
        'user_count': len([u for u in receipt['billed_users'] if u['cost'] > 0]),
        'asset_count': len([a for a in receipt['billed_assets'] if a['cost'] > 0]),
        'billable_hours': float(receipt.get('billable_hours', 0)),
        'billing_data_json': billing_data,  # Complete breakdown
        'invoice_csv': csv_content,
        'line_items': line_items,
        'created_by': user_email,
        'notes': notes
    }

    return payload


def send_to_archive(account_number, year, month, user_email=None, notes=None):
    """
    Calculate billing and send snapshot to Archive service.

    Returns:
        tuple: (success: bool, message: str, invoice_number: str or None)
    """
    # Generate snapshot payload
    payload = create_snapshot_payload(account_number, year, month, user_email, notes)

    if not payload:
        return False, "Unable to calculate billing for this company", None

    # Send to Archive service
    try:
        response = call_service('archive', '/api/snapshot', method='POST', json=payload)

        if response.status_code == 201:
            result = response.json()
            return True, "Bill accepted and archived successfully", result.get('invoice_number')
        elif response.status_code == 409:
            return False, "This bill has already been archived", payload['invoice_number']
        else:
            return False, f"Archive service error: {response.text}", None

    except Exception as e:
        return False, f"Failed to connect to Archive service: {str(e)}", None


def check_if_archived(invoice_number):
    """
    Check if a bill has already been archived.

    Returns:
        bool: True if archived, False if not
    """
    try:
        response = call_service('archive', f'/api/snapshot/{invoice_number}', method='GET')
        return response.status_code == 200
    except:
        return False
