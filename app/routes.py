from flask import render_template, g, jsonify, request, redirect, url_for, flash, Response
from app import app
from app.auth import token_required, billing_required, admin_required
from app.codex_client import get_all_companies, get_all_companies_with_details, get_billing_data_from_codex
from app.billing_engine import get_billing_data_for_client
from datetime import datetime, timedelta
from models import BillingPlan, ClientBillingOverride, ManualAsset, ManualUser, CustomLineItem, AssetBillingOverride, UserBillingOverride, TicketDetail
from extensions import db
import io
import csv
import zipfile


@app.route('/')
@billing_required
def index():
    """Billing dashboard - shows all clients with their billing data."""
    # Prevent service calls from accessing UI routes
    if g.is_service_call:
        return {'error': 'This endpoint is for users only'}, 403

    user = g.user
    today = datetime.now()

    return render_template('index.html',
        user=user,
        current_year=today.year,
        current_month=today.month
    )


@app.route('/client/<account_number>')
@billing_required
def client_details(account_number):
    """Client billing details and breakdown."""
    if g.is_service_call:
        return {'error': 'This endpoint is for users only'}, 403

    # Fetch data from Codex
    codex_data = get_billing_data_from_codex(account_number)
    if not codex_data:
        return render_template('error.html', message=f"Company {account_number} not found"), 404

    # Get current month/year for default billing period
    today = datetime.now()
    year = request.args.get('year', today.year, type=int)
    month = request.args.get('month', today.month, type=int)

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
        return render_template('error.html',
            message=f"Unable to calculate billing for {account_number}. Check billing plan configuration."), 500

    return render_template('client_details.html',
        user=g.user,
        data=billing_data,
        year=year,
        month=month,
        account_number=account_number
    )


@app.route('/client/<account_number>/settings', methods=['GET', 'POST'])
@billing_required
def client_settings(account_number):
    """Client billing settings - manage overrides and custom items."""
    if g.is_service_call:
        return {'error': 'This endpoint is for users only'}, 403

    codex_data = get_billing_data_from_codex(account_number)
    if not codex_data:
        return render_template('error.html', message=f"Company {account_number} not found"), 404

    # Handle POST requests
    if request.method == 'POST':
        action = request.form.get('action')

        # Handle deletions via query params
        if request.args.get('delete_manual_asset'):
            asset_id = request.args.get('delete_manual_asset')
            asset = ManualAsset.query.get(asset_id)
            if asset and asset.company_account_number == account_number:
                db.session.delete(asset)
                db.session.commit()
                flash('Manual asset deleted', 'success')
            return redirect(url_for('client_settings', account_number=account_number))

        if request.args.get('delete_manual_user'):
            user_id = request.args.get('delete_manual_user')
            user = ManualUser.query.get(user_id)
            if user and user.company_account_number == account_number:
                db.session.delete(user)
                db.session.commit()
                flash('Manual user deleted', 'success')
            return redirect(url_for('client_settings', account_number=account_number))

        if request.args.get('delete_line_item'):
            item_id = request.args.get('delete_line_item')
            item = CustomLineItem.query.get(item_id)
            if item and item.company_account_number == account_number:
                db.session.delete(item)
                db.session.commit()
                flash('Line item deleted', 'success')
            return redirect(url_for('client_settings', account_number=account_number))

        # Handle adding manual asset
        if action == 'add_manual_asset':
            hostname = request.form.get('manual_asset_hostname')
            billing_type = request.form.get('manual_asset_billing_type')
            custom_cost = request.form.get('manual_asset_custom_cost')

            if hostname:
                asset = ManualAsset(
                    company_account_number=account_number,
                    hostname=hostname,
                    billing_type=billing_type,
                    custom_cost=float(custom_cost) if custom_cost else None
                )
                db.session.add(asset)
                db.session.commit()
                flash('Manual asset added', 'success')
            return redirect(url_for('client_settings', account_number=account_number))

        # Handle adding manual user
        if action == 'add_manual_user':
            name = request.form.get('manual_user_name')
            billing_type = request.form.get('manual_user_billing_type')
            custom_cost = request.form.get('manual_user_custom_cost')

            if name:
                user = ManualUser(
                    company_account_number=account_number,
                    full_name=name,
                    billing_type=billing_type,
                    custom_cost=float(custom_cost) if custom_cost else None
                )
                db.session.add(user)
                db.session.commit()
                flash('Manual user added', 'success')
            return redirect(url_for('client_settings', account_number=account_number))

        # Handle adding line item
        if action == 'add_line_item':
            name = request.form.get('line_item_name')
            item_type = request.form.get('line_item_type')

            if name:
                item = CustomLineItem(company_account_number=account_number, name=name)

                if item_type == 'recurring':
                    fee = request.form.get('line_item_recurring_fee')
                    item.monthly_fee = float(fee) if fee else None
                elif item_type == 'one_off':
                    fee = request.form.get('line_item_one_off_fee')
                    month = request.form.get('line_item_one_off_month')
                    item.one_off_fee = float(fee) if fee else None
                    item.one_off_month = int(month) if month else None
                    item.one_off_year = datetime.now().year
                elif item_type == 'yearly':
                    fee = request.form.get('line_item_yearly_fee')
                    month = request.form.get('line_item_yearly_month')
                    item.yearly_fee = float(fee) if fee else None
                    item.yearly_bill_month = int(month) if month else None

                db.session.add(item)
                db.session.commit()
                flash('Line item added', 'success')
            return redirect(url_for('client_settings', account_number=account_number))

        # Handle saving all overrides
        if action == 'save_overrides':
            # Get or create ClientBillingOverride
            rate_override = ClientBillingOverride.query.filter_by(
                company_account_number=account_number
            ).first()
            if not rate_override:
                rate_override = ClientBillingOverride(company_account_number=account_number)
                db.session.add(rate_override)

            # Save billing plan override
            rate_override.override_billing_plan_enabled = 'override_billing_plan_enabled' in request.form
            rate_override.billing_plan = request.form.get('billing_plan') or None

            # Save support level override
            rate_override.override_support_level_enabled = 'override_support_level_enabled' in request.form
            rate_override.support_level = request.form.get('support_level') or None

            # Save all rate overrides
            rate_fields = [
                ('per_user_cost', 'puc'), ('per_workstation_cost', 'pwc'), ('per_server_cost', 'psc'),
                ('per_vm_cost', 'pvc'), ('per_switch_cost', 'pswitchc'), ('per_firewall_cost', 'pfirewallc'),
                ('per_hour_ticket_cost', 'phtc'), ('backup_base_fee_workstation', 'bbfw'),
                ('backup_base_fee_server', 'bbfs'), ('backup_included_tb', 'bit'), ('backup_per_tb_fee', 'bpt'),
                ('prepaid_hours_monthly', 'prepaid_hours_monthly'), ('prepaid_hours_yearly', 'prepaid_hours_yearly')
            ]

            for field_name, short_name in rate_fields:
                enabled_field = f'override_{short_name}_enabled'
                setattr(rate_override, enabled_field, enabled_field in request.form)

                value = request.form.get(field_name)
                if value:
                    setattr(rate_override, field_name, float(value))
                else:
                    setattr(rate_override, field_name, None)

            # Save asset overrides
            for asset in codex_data['assets']:
                asset_id = asset.get('id')
                billing_type = request.form.get(f'asset_billing_type_{asset_id}')
                custom_cost = request.form.get(f'asset_custom_cost_{asset_id}')

                if billing_type:  # Only save if override is set
                    override = AssetBillingOverride.query.filter_by(asset_id=asset_id).first()
                    if not override:
                        override = AssetBillingOverride(asset_id=asset_id)
                        db.session.add(override)
                    override.billing_type = billing_type
                    override.custom_cost = float(custom_cost) if custom_cost else None
                else:
                    # Remove override if cleared
                    override = AssetBillingOverride.query.filter_by(asset_id=asset_id).first()
                    if override:
                        db.session.delete(override)

            # Save user overrides
            for user in codex_data['users']:
                user_id = user.get('id')
                billing_type = request.form.get(f'user_billing_type_{user_id}')
                custom_cost = request.form.get(f'user_custom_cost_{user_id}')

                if billing_type:  # Only save if override is set
                    override = UserBillingOverride.query.filter_by(user_id=user_id).first()
                    if not override:
                        override = UserBillingOverride(user_id=user_id)
                        db.session.add(override)
                    override.billing_type = billing_type
                    override.custom_cost = float(custom_cost) if custom_cost else None
                else:
                    # Remove override if cleared
                    override = UserBillingOverride.query.filter_by(user_id=user_id).first()
                    if override:
                        db.session.delete(override)

            db.session.commit()
            flash('Settings saved successfully', 'success')
            return redirect(url_for('client_settings', account_number=account_number))

    # GET request - display form
    rate_override = ClientBillingOverride.query.filter_by(
        company_account_number=account_number
    ).first()
    manual_assets = ManualAsset.query.filter_by(company_account_number=account_number).all()
    manual_users = ManualUser.query.filter_by(company_account_number=account_number).all()
    custom_items = CustomLineItem.query.filter_by(company_account_number=account_number).all()

    # Get default plan rates for display
    billing_plan_name = codex_data['company'].get('billing_plan') or ''
    contract_term = codex_data['company'].get('contract_term_length') or 'Month to Month'
    defaults = BillingPlan.query.filter_by(
        billing_plan=billing_plan_name,
        term_length=contract_term
    ).first()

    # Get available billing plans
    billing_plans = BillingPlan.query.with_entities(
        BillingPlan.billing_plan, BillingPlan.term_length
    ).distinct().all()

    # Get asset/user overrides
    asset_overrides = {o.asset_id: o for o in AssetBillingOverride.query.all()}
    user_overrides = {o.user_id: o for o in UserBillingOverride.query.all()}

    return render_template('client_settings.html',
        user=g.user,
        company=codex_data['company'],
        assets=codex_data['assets'],
        users=codex_data['users'],
        rate_override=rate_override,
        manual_assets=manual_assets,
        manual_users=manual_users,
        custom_items=custom_items,
        billing_plans=billing_plans,
        defaults=defaults,
        asset_overrides=asset_overrides,
        user_overrides=user_overrides
    )




# --- API Endpoints ---

@app.route('/api/billing/<account_number>')
@token_required
def api_billing(account_number):
    """
    API endpoint to get billing data for a specific company.
    Works for both user and service calls.
    """
    year = request.args.get('year', datetime.now().year, type=int)
    month = request.args.get('month', datetime.now().month, type=int)

    # Fetch from Codex
    codex_data = get_billing_data_from_codex(account_number)
    if not codex_data:
        return {'error': f'Company {account_number} not found'}, 404

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
        return {'error': 'Unable to calculate billing. Check plan configuration.'}, 500

    # Return just the receipt data for API calls
    return jsonify({
        'account_number': account_number,
        'company_name': codex_data['company'].get('name'),
        'billing_period': f'{year}-{month:02d}',
        'receipt': billing_data['receipt_data'],
        'quantities': billing_data['quantities'],
        'effective_rates': billing_data['effective_rates']
    })


@app.route('/api/billing/dashboard')
@token_required
def api_billing_dashboard():
    """
    API endpoint to get billing dashboard data for all companies.
    Uses bulk endpoint to minimize API calls.
    """
    year = request.args.get('year', datetime.now().year, type=int)
    month = request.args.get('month', datetime.now().month, type=int)

    # Try bulk endpoint first (1 API call instead of 5N+1)
    # Include tickets for current year to avoid separate queries
    companies_bulk = get_all_companies_with_details(include_tickets=True, year=datetime.now().year)

    # If bulk endpoint not available, fall back to individual calls
    if companies_bulk is None:
        companies = get_all_companies()
        if not companies:
            return jsonify({
                'billing_period': f'{year}-{month:02d}',
                'companies': [],
                'warning': 'No companies available. Codex service may not be running or configured.'
            })

        # Fall back to individual API calls per company
        dashboard_data = []
        for company in companies:
            account_number = company.get('account_number')
            if not account_number:
                continue

            codex_data = get_billing_data_from_codex(account_number)
            if not codex_data:
                continue

            # Fetch tickets from Codex
            from app.codex_client import get_company_tickets
            tickets = get_company_tickets(account_number, year=datetime.now().year)

            billing_data = get_billing_data_for_client(
                codex_data['company'],
                codex_data['assets'],
                codex_data['users'],
                year,
                month,
                tickets_data=tickets
            )

            if not billing_data:
                continue

            # Calculate yearly hours
            hours_this_year = sum(float(t.get('total_hours_spent', 0)) for t in tickets)

            dashboard_data.append({
                'account_number': account_number,
                'name': company.get('name'),
                'billing_plan': billing_data['client'].get('billing_plan'),
                'support_level': billing_data.get('support_level_display', 'N/A'),
                'contract_term_length': billing_data['client'].get('contract_term_length', 'N/A'),
                'contract_end_date': billing_data.get('contract_end_date', 'N/A'),
                'total_bill': billing_data['receipt_data']['total'],
                'workstations': billing_data['quantities'].get('workstation', 0),
                'servers': billing_data['quantities'].get('server', 0),
                'vms': billing_data['quantities'].get('vm', 0),
                'users': billing_data['quantities'].get('regular_users', 0),
                'backup': round(billing_data.get('total_backup_tb', 0), 2),
                'hours': round(hours_this_year, 2),
            })

        return jsonify({
            'billing_period': f'{year}-{month:02d}',
            'companies': dashboard_data
        })

    # Use bulk data (optimized path)
    if not companies_bulk:
        return jsonify({
            'billing_period': f'{year}-{month:02d}',
            'companies': [],
            'warning': 'No companies available. Codex service may not be running or configured.'
        })

    dashboard_data = []
    for item in companies_bulk:
        company = item.get('company')
        if not company or not company.get('account_number'):
            continue

        # Calculate billing using bulk-fetched data including tickets
        tickets = item.get('tickets', [])
        billing_data = get_billing_data_for_client(
            company,
            item.get('assets', []),
            item.get('contacts', []),
            year,
            month,
            tickets_data=tickets
        )

        if not billing_data:
            continue

        # Calculate yearly hours from bulk-fetched tickets
        account_number = company.get('account_number')
        hours_this_year = sum(float(t.get('total_hours_spent', 0)) for t in tickets)

        dashboard_data.append({
            'account_number': account_number,
            'name': company.get('name'),
            'billing_plan': billing_data['client'].get('billing_plan'),
            'support_level': billing_data.get('support_level_display', 'N/A'),
            'contract_term_length': billing_data['client'].get('contract_term_length', 'N/A'),
            'contract_end_date': billing_data.get('contract_end_date', 'N/A'),
            'total_bill': billing_data['receipt_data']['total'],
            'workstations': billing_data['quantities'].get('workstation', 0),
            'servers': billing_data['quantities'].get('server', 0),
            'vms': billing_data['quantities'].get('vm', 0),
            'users': billing_data['quantities'].get('regular_users', 0),
            'backup': round(billing_data.get('total_backup_tb', 0), 2),
            'hours': round(hours_this_year, 2),
        })

    return jsonify({
        'billing_period': f'{year}-{month:02d}',
        'companies': dashboard_data
    })


@app.route('/api/plans')
@token_required
def api_plans():
    """API endpoint to list all billing plans."""
    plans = BillingPlan.query.all()
    return jsonify([{
        'id': p.id,
        'billing_plan': p.billing_plan,
        'term_length': p.term_length,
        'support_level': p.support_level,
        'per_user_cost': float(p.per_user_cost or 0),
        'per_workstation_cost': float(p.per_workstation_cost or 0),
        'per_server_cost': float(p.per_server_cost or 0),
    } for p in plans])


# --- Export Routes ---

def generate_quickbooks_csv(billing_data):
    """Generate a QuickBooks-compatible CSV for a single client."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['InvoiceNo', 'Customer', 'InvoiceDate', 'DueDate', 'Item(Product/Service)', 'Description', 'Qty', 'Rate', 'Amount'])

    receipt = billing_data['receipt_data']
    client_name = billing_data['client']['name']
    account_number = billing_data['client']['account_number']
    invoice_date = datetime.now().strftime('%Y-%m-%d')
    due_date = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
    invoice_number = f"{account_number}-{datetime.now().strftime('%Y%m')}"

    # Add user charges
    for user in receipt['billed_users']:
        writer.writerow([
            invoice_number, client_name, invoice_date, due_date,
            'Managed Services',
            f"User: {user['name']} ({user['type']})",
            1, f"{user['cost']:.2f}", f"{user['cost']:.2f}"
        ])

    # Add asset charges
    for asset in receipt['billed_assets']:
        writer.writerow([
            invoice_number, client_name, invoice_date, due_date,
            'Managed Services',
            f"Asset: {asset['name']} ({asset['type']})",
            1, f"{asset['cost']:.2f}", f"{asset['cost']:.2f}"
        ])

    # Add custom line items
    for item in receipt['billed_line_items']:
        writer.writerow([
            invoice_number, client_name, invoice_date, due_date,
            'Custom Services',
            f"Custom Item: {item['name']} ({item['type']})",
            1, f"{item['cost']:.2f}", f"{item['cost']:.2f}"
        ])

    # Add ticket charges
    if receipt['ticket_charge'] > 0:
        writer.writerow([
            invoice_number, client_name, invoice_date, due_date,
            'Hourly Labor',
            f"Billable Hours ({receipt['billable_hours']:.2f} hrs)",
            f"{receipt['billable_hours']:.2f}",
            f"{billing_data['effective_rates']['per_hour_ticket_cost']:.2f}",
            f"{receipt['ticket_charge']:.2f}"
        ])

    # Add backup charges
    if receipt['backup_charge'] > 0:
        if receipt.get('backup_base_workstation', 0) > 0:
            backed_up_workstations = sum(
                1 for a in billing_data['assets']
                if a.get('billing_type') == 'Workstation' and a.get('backup_data_bytes', 0) > 0
            )
            writer.writerow([
                invoice_number, client_name, invoice_date, due_date,
                'Backup Services',
                'Workstation Backup Base Fee',
                backed_up_workstations,
                f"{billing_data['effective_rates']['backup_base_fee_workstation']:.2f}",
                f"{receipt['backup_base_workstation']:.2f}"
            ])

        if receipt.get('backup_base_server', 0) > 0:
            backed_up_servers = sum(
                1 for a in billing_data['assets']
                if a.get('billing_type') in ['Server', 'VM'] and a.get('backup_data_bytes', 0) > 0
            )
            writer.writerow([
                invoice_number, client_name, invoice_date, due_date,
                'Backup Services',
                'Server Backup Base Fee',
                backed_up_servers,
                f"{billing_data['effective_rates']['backup_base_fee_server']:.2f}",
                f"{receipt['backup_base_server']:.2f}"
            ])

        if receipt.get('overage_charge', 0) > 0:
            writer.writerow([
                invoice_number, client_name, invoice_date, due_date,
                'Backup Services',
                f"Storage Overage ({receipt['overage_tb']:.2f} TB)",
                f"{receipt['overage_tb']:.2f}",
                f"{billing_data['effective_rates']['backup_per_tb_fee']:.2f}",
                f"{receipt['overage_charge']:.2f}"
            ])

    return output.getvalue()


@app.route('/client/<account_number>/export/quickbooks')
@billing_required
def export_quickbooks_csv(account_number):
    """Export a single client's billing data as QuickBooks CSV."""
    if g.is_service_call:
        return {'error': 'This endpoint is for users only'}, 403

    year = request.args.get('year', datetime.now().year, type=int)
    month = request.args.get('month', datetime.now().month, type=int)

    # Fetch data from Codex
    codex_data = get_billing_data_from_codex(account_number)
    if not codex_data:
        flash(f"Could not generate export for client {account_number}.", 'error')
        return redirect(url_for('index'))

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
        flash(f"Could not generate export for client {account_number}.", 'error')
        return redirect(url_for('index'))

    csv_content = generate_quickbooks_csv(billing_data)

    return Response(
        csv_content,
        mimetype="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=quickbooks_export_{account_number}_{year}-{month:02d}.csv"
        }
    )


@app.route('/export/all_bills', methods=['POST'])
@admin_required
def export_all_bills_zip():
    """Export all clients' billing data as a ZIP of QuickBooks CSVs."""
    if g.is_service_call:
        return {'error': 'This endpoint is for users only'}, 403

    year = int(request.form.get('year', datetime.now().year))
    month = int(request.form.get('month', datetime.now().month))

    # Get all companies with tickets for the year
    companies_bulk = get_all_companies_with_details(include_tickets=True, year=year)
    if not companies_bulk:
        companies_bulk = []
        all_companies = get_all_companies()
        if all_companies:
            for company in all_companies:
                account_number = company.get('account_number')
                if account_number:
                    codex_data = get_billing_data_from_codex(account_number)
                    if codex_data:
                        companies_bulk.append(codex_data)

    if not companies_bulk:
        flash("No clients found to export.", "error")
        return redirect(url_for('index'))

    # Create ZIP file in memory
    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        for item in companies_bulk:
            company = item.get('company') if 'company' in item else item
            if not company or not company.get('account_number'):
                continue

            account_number = company.get('account_number')

            # Calculate billing with bulk-fetched tickets
            billing_data = get_billing_data_for_client(
                company,
                item.get('assets', []),
                item.get('users', []) or item.get('contacts', []),
                year,
                month,
                tickets_data=item.get('tickets', [])
            )

            if billing_data:
                csv_content = generate_quickbooks_csv(billing_data)
                sanitized_name = company.get('name', 'Unknown').replace('/', '_').replace(' ', '_')
                file_name = f"{sanitized_name}_{year}-{month:02d}.csv"
                zf.writestr(file_name, csv_content)

    memory_file.seek(0)

    return Response(
        memory_file,
        mimetype='application/zip',
        headers={
            'Content-Disposition': f'attachment;filename=all_invoices_{year}-{month:02d}.zip'
        }
    )

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for monitoring"""
    return {
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat()
    }
