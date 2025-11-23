"""
Snapshot Creation Module

Replaces the old archive_client.py service calls with direct database writes.
Creates immutable billing snapshots in the local database.
"""

from extensions import db
from models import BillingSnapshot, SnapshotLineItem
from app.codex_client import get_billing_data_from_codex
from app.billing_engine import get_billing_data_for_client
from app.invoice_generator import generate_invoice_csv, generate_invoice_number
from datetime import datetime, timedelta
import calendar
import json


def create_snapshot(account_number, year, month, user_email=None, notes=None):
    """
    Calculate billing and create snapshot directly in database.

    This replaces the old archive_client.py send_to_archive() function.
    Instead of making HTTP calls to Archive service, we write directly to DB.

    Args:
        account_number: Company account number
        year: Billing year
        month: Billing month
        user_email: Who's creating this snapshot (optional)
        notes: Optional notes about this snapshot

    Returns:
        tuple: (success: bool, message: str, invoice_number: str or None)
    """
    # Get billing data from Codex
    codex_data = get_billing_data_from_codex(account_number)
    if not codex_data:
        return False, "Unable to fetch company data from Codex", None

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
        return False, "Unable to calculate billing for this company", None

    # Generate CSV invoice
    csv_content, company_name, invoice_number = generate_invoice_csv(account_number, year, month)
    if not csv_content:
        return False, "Unable to generate invoice CSV", None

    # Check if snapshot already exists
    existing = BillingSnapshot.query.filter_by(invoice_number=invoice_number).first()
    if existing:
        return False, "This bill has already been archived", invoice_number

    # Calculate dates
    _, last_day = calendar.monthrange(year, month)
    invoice_date = datetime(year, month, last_day).strftime('%Y-%m-%d')
    due_date = (datetime(year, month, last_day) + timedelta(days=30)).strftime('%Y-%m-%d')

    # Extract receipt data
    receipt = billing_data['receipt_data']
    company = billing_data['client']

    # Create snapshot
    snapshot = BillingSnapshot(
        company_account_number=account_number,
        company_name=company_name,
        invoice_number=invoice_number,
        billing_year=year,
        billing_month=month,
        invoice_date=invoice_date,
        due_date=due_date,
        archived_at=datetime.now().isoformat(),
        billing_plan=company.get('billing_plan'),
        contract_term=company.get('contract_term_length'),
        support_level=billing_data.get('support_level_display'),
        total_amount=float(receipt['total']),
        total_user_charges=float(receipt['total_user_charges']),
        total_asset_charges=float(receipt['total_asset_charges']),
        total_backup_charges=float(receipt.get('backup_charge', 0)),
        total_ticket_charges=float(receipt.get('ticket_charge', 0)),
        total_line_item_charges=float(receipt.get('total_line_item_charges', 0)),
        user_count=len([u for u in receipt['billed_users'] if u['cost'] > 0]),
        asset_count=len([a for a in receipt['billed_assets'] if a['cost'] > 0]),
        billable_hours=float(receipt.get('billable_hours', 0)),
        billing_data_json=json.dumps(billing_data),
        invoice_csv=csv_content,
        created_by=user_email,
        notes=notes
    )

    db.session.add(snapshot)
    db.session.flush()  # Get snapshot ID

    # Create line items
    # Add user line items
    for user in receipt['billed_users']:
        if user['cost'] > 0:
            line_item = SnapshotLineItem(
                snapshot_id=snapshot.id,
                line_type='user',
                item_name=user['name'],
                description=f"User: {user['name']} ({user['type']})",
                quantity=1.0,
                rate=user['cost'],
                amount=user['cost']
            )
            db.session.add(line_item)

    # Add asset line items
    for asset in receipt['billed_assets']:
        if asset['cost'] > 0:
            line_item = SnapshotLineItem(
                snapshot_id=snapshot.id,
                line_type='asset',
                item_name=asset['name'],
                description=f"Asset: {asset['name']} ({asset['type']})",
                quantity=1.0,
                rate=asset['cost'],
                amount=asset['cost']
            )
            db.session.add(line_item)

    # Add backup charges
    if receipt.get('backup_charge', 0) > 0:
        line_item = SnapshotLineItem(
            snapshot_id=snapshot.id,
            line_type='backup',
            item_name='Backup Services',
            description=f"Backup charges (base + {receipt.get('overage_tb', 0):.2f} TB overage)",
            quantity=1.0,
            rate=receipt['backup_charge'],
            amount=receipt['backup_charge']
        )
        db.session.add(line_item)

    # Add ticket charges
    if receipt.get('billable_hours', 0) > 0:
        hours = receipt['billable_hours']
        per_hour = receipt['ticket_charge'] / hours if hours > 0 else 0
        line_item = SnapshotLineItem(
            snapshot_id=snapshot.id,
            line_type='ticket',
            item_name='Billable Hours',
            description=f"Billable Hours ({hours:.2f} hrs)",
            quantity=hours,
            rate=per_hour,
            amount=receipt['ticket_charge']
        )
        db.session.add(line_item)

    # Add custom line items
    for item in receipt['billed_line_items']:
        line_item = SnapshotLineItem(
            snapshot_id=snapshot.id,
            line_type='custom',
            item_name=item['name'],
            description=f"{item['name']} ({item['type']})",
            quantity=1.0,
            rate=item['cost'],
            amount=item['cost']
        )
        db.session.add(line_item)

    try:
        db.session.commit()
        return True, "Bill accepted and archived successfully", invoice_number
    except Exception as e:
        db.session.rollback()
        from app.helm_logger import get_helm_logger
        logger = get_helm_logger()
        if logger:
            logger.error(f"Failed to create snapshot: {str(e)}")
        return False, "Internal server error", None


def check_if_archived(invoice_number):
    """
    Check if a bill has already been archived.

    Returns:
        bool: True if archived, False if not
    """
    snapshot = BillingSnapshot.query.filter_by(invoice_number=invoice_number).first()
    return snapshot is not None
