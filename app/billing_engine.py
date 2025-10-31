from collections import defaultdict
from datetime import datetime, timezone, timedelta
import calendar
from extensions import db
from models import (
    ClientBillingOverride, AssetBillingOverride, UserBillingOverride,
    ManualAsset, ManualUser, CustomLineItem, TicketDetail, ClientFeatureOverride
)
from app.codex_client import get_billing_plan_from_codex


def get_billing_data_for_client(company_data, assets_data, users_data, year, month, tickets_data=None, plan_features_cache=None):
    """
    A comprehensive function to calculate billing details for a specific client and period.
    This is the core logic that powers both the dashboard and the breakdown view.

    Args:
        company_data: Company dict from Codex (includes account_number, billing_plan, etc.)
        assets_data: List of asset dicts from Codex
        users_data: List of user/contact dicts from Codex
        year: Billing year
        month: Billing month (1-12)
        tickets_data: List of ticket dicts from Codex (optional, will fetch from Codex if None)
        plan_features_cache: Dict of plan features from bulk API (optional, for performance)

    Returns:
        Dict with billing breakdown and all related data
    """
    account_number = company_data.get('account_number')
    if not account_number:
        return None

    # Default contract term to 'Month to Month' if not set
    if not company_data.get('contract_term_length'):
        company_data['contract_term_length'] = 'Month to Month'

    # Fetch manual assets and users from ledger database
    manual_assets = ManualAsset.query.filter_by(company_account_number=account_number).all()
    manual_users = ManualUser.query.filter_by(company_account_number=account_number).all()
    custom_line_items = CustomLineItem.query.filter_by(company_account_number=account_number).all()

    # Fetch overrides
    asset_overrides = {
        override.asset_id: override
        for override in AssetBillingOverride.query.all()
    }
    user_overrides = {
        override.user_id: override
        for override in UserBillingOverride.query.all()
    }
    rate_overrides = ClientBillingOverride.query.filter_by(
        company_account_number=account_number
    ).first()

    # Determine the effective billing plan
    billing_plan_name = (company_data.get('billing_plan') or '').strip()
    if rate_overrides and rate_overrides.override_billing_plan_enabled and rate_overrides.billing_plan:
        billing_plan_name = rate_overrides.billing_plan

    company_data['billing_plan'] = billing_plan_name

    contract_term = (company_data.get('contract_term_length') or '').strip()

    # Fetch plan details from Codex instead of local database
    plan_details_dict = get_billing_plan_from_codex(billing_plan_name, contract_term)

    if not plan_details_dict:
        return None

    # Convert dict to object-like structure for compatibility
    class PlanDetails:
        def __init__(self, data):
            self.support_level = data.get('support_level', 'Billed Hourly')
            self.per_user_cost = data.get('per_user_cost', 0)
            self.per_workstation_cost = data.get('per_workstation_cost', 0)
            self.per_server_cost = data.get('per_server_cost', 0)
            self.per_vm_cost = data.get('per_vm_cost', 0)
            self.per_switch_cost = data.get('per_switch_cost', 0)
            self.per_firewall_cost = data.get('per_firewall_cost', 0)
            self.per_hour_ticket_cost = data.get('per_hour_ticket_cost', 0)
            self.backup_base_fee_workstation = data.get('backup_base_fee_workstation', 0)
            self.backup_base_fee_server = data.get('backup_base_fee_server', 0)
            self.backup_included_tb = data.get('backup_included_tb', 1.0)
            self.backup_per_tb_fee = data.get('backup_per_tb_fee', 0)

    plan_details = PlanDetails(plan_details_dict)

    # Use provided tickets or fetch from Codex
    if tickets_data is None:
        # Fallback: try to fetch from Codex (requires importing codex_client)
        from app.codex_client import get_company_tickets
        tickets_data = get_company_tickets(account_number, year=datetime.now().year)

    # Convert ticket dicts to objects for compatibility
    class TicketObj:
        def __init__(self, data):
            self.ticket_id = data.get('ticket_id')
            self.ticket_number = data.get('ticket_number')
            self.subject = data.get('subject')
            self.last_updated_at = data.get('last_updated_at')
            self.closed_at = data.get('closed_at')
            self.total_hours_spent = data.get('total_hours_spent', 0)

    all_tickets_this_year = [TicketObj(t) for t in tickets_data] if tickets_data else []

    # --- Determine the Effective Billing Rates ---
    effective_rates = {
        'support_level': plan_details.support_level,
        'per_user_cost': float(plan_details.per_user_cost or 0),
        'per_workstation_cost': float(plan_details.per_workstation_cost or 0),
        'per_server_cost': float(plan_details.per_server_cost or 0),
        'per_vm_cost': float(plan_details.per_vm_cost or 0),
        'per_switch_cost': float(plan_details.per_switch_cost or 0),
        'per_firewall_cost': float(plan_details.per_firewall_cost or 0),
        'per_hour_ticket_cost': float(plan_details.per_hour_ticket_cost or 0),
        'backup_base_fee_workstation': float(plan_details.backup_base_fee_workstation or 0),
        'backup_base_fee_server': float(plan_details.backup_base_fee_server or 0),
        'backup_included_tb': float(plan_details.backup_included_tb or 1),
        'backup_per_tb_fee': float(plan_details.backup_per_tb_fee or 0),
    }

    # Apply client-specific rate overrides
    if rate_overrides:
        rate_key_map = {
            'puc': 'per_user_cost', 'psc': 'per_server_cost', 'pwc': 'per_workstation_cost',
            'pvc': 'per_vm_cost', 'pswitchc': 'per_switch_cost', 'pfirewallc': 'per_firewall_cost',
            'phtc': 'per_hour_ticket_cost', 'bbfw': 'backup_base_fee_workstation',
            'bbfs': 'backup_base_fee_server', 'bit': 'backup_included_tb', 'bpt': 'backup_per_tb_fee'
        }

        if rate_overrides.override_support_level_enabled:
            effective_rates['support_level'] = rate_overrides.support_level

        for short_key, rate_key in rate_key_map.items():
            if getattr(rate_overrides, f'override_{short_key}_enabled', False):
                value = getattr(rate_overrides, rate_key)
                if value is not None:
                    effective_rates[rate_key] = float(value)

    support_level_display = effective_rates.get('support_level', 'Billed Hourly')

    # --- Calculate Contract End Date ---
    contract_end_date = "N/A"
    contract_expired = False
    if company_data.get('contract_start_date') and company_data.get('contract_term_length'):
        try:
            start_date_str = str(company_data['contract_start_date']).split('T')[0]
            start_date = datetime.fromisoformat(start_date_str)
            term = company_data['contract_term_length']

            years_to_add = {'1-Year': 1, '2-Year': 2, '3-Year': 3}.get(term, 0)
            if years_to_add > 0:
                end_date = start_date.replace(year=start_date.year + years_to_add) - timedelta(days=1)
                contract_end_date = end_date.strftime('%Y-%m-%d')
                if datetime.now().date() > end_date.date():
                    contract_expired = True
            elif term == 'Month to Month':
                contract_end_date = "Month to Month"
        except (ValueError, TypeError):
            contract_end_date = "Invalid Start Date"

    # --- Fetch Plan Features from Cache ---
    plan_features = {}
    if plan_features_cache and billing_plan_name and contract_term:
        cache_key = f"{billing_plan_name}|{contract_term}"
        plan_features = plan_features_cache.get(cache_key, {})

    # Check for feature overrides from Ledger database
    feature_overrides = ClientFeatureOverride.query.filter_by(
        company_account_number=account_number
    ).all()

    # Build effective features (plan defaults + overrides)
    effective_features = {
        'antivirus': plan_features.get('antivirus', 'Not Included'),
        'soc': plan_features.get('soc', 'Not Included'),
        'password_manager': plan_features.get('password_manager', 'Not Included'),
        'sat': plan_features.get('sat', 'Not Included'),
        'email_security': plan_features.get('email_security', 'Not Included'),
        'network_management': plan_features.get('network_management', 'Not Included'),
    }

    # Apply Ledger-specific feature overrides and track which features are overridden
    feature_override_status = {}
    for override in feature_overrides:
        if override.override_enabled and override.value:
            effective_features[override.feature_type] = override.value
            feature_override_status[override.feature_type] = True

    # --- Calculate Itemized Asset Charges ---
    billed_assets = []
    quantities = defaultdict(int)
    all_assets = list(assets_data) + [
        {'id': a.id, 'hostname': a.hostname, 'billing_type': a.billing_type,
         'custom_cost': a.custom_cost, 'backup_data_bytes': 0}
        for a in manual_assets
    ]
    total_asset_charges = 0.0

    for asset in all_assets:
        is_manual = 'datto_uid' not in asset
        override = asset_overrides.get(asset.get('id')) if not is_manual else None

        if is_manual:
            # Manual assets have billing_type directly
            billing_type = asset.get('billing_type', 'Workstation')
        else:
            # Codex assets may have overrides
            billing_type = override.billing_type if override else asset.get('billing_type', 'Workstation')

        cost = 0.0
        if billing_type == 'Custom':
            if is_manual:
                cost = float(asset.get('custom_cost') or 0.0)
            elif override:
                cost = float(override.custom_cost or 0.0)
        elif billing_type != 'No Charge':
            rate_key = f"per_{billing_type.lower()}_cost"
            cost = float(effective_rates.get(rate_key, 0.0) or 0.0)

        total_asset_charges += cost
        quantities[billing_type.lower()] += 1
        billed_assets.append({'name': asset.get('hostname'), 'type': billing_type, 'cost': cost})

    # --- Calculate Itemized User Charges ---
    billed_users = []
    all_users = list(users_data) + [
        {'id': u.id, 'full_name': u.full_name, 'billing_type': u.billing_type, 'custom_cost': u.custom_cost}
        for u in manual_users
    ]
    total_user_charges = 0.0

    for user in all_users:
        is_manual = 'freshservice_id' not in user and 'email' not in user
        override = user_overrides.get(user.get('id')) if not is_manual else None

        if is_manual:
            billing_type = user.get('billing_type', 'Paid')
        else:
            billing_type = override.billing_type if override else 'Paid'

        cost = 0.0
        if billing_type == 'Custom':
            if is_manual:
                cost = float(user.get('custom_cost') or 0.0)
            elif override:
                cost = float(override.custom_cost or 0.0)
        elif billing_type == 'Paid':
            cost = float(effective_rates.get('per_user_cost', 0.0) or 0.0)

        total_user_charges += cost
        quantities['regular_users' if billing_type == 'Paid' else 'free_users'] += 1
        user_name = user.get('full_name') or user.get('name', 'Unknown')
        billed_users.append({'name': user_name, 'type': billing_type, 'cost': cost})

    # --- Calculate Ticket Charges for the specified billing period ---
    _, num_days = calendar.monthrange(year, month)
    start_of_billing_month = datetime(year, month, 1, tzinfo=timezone.utc)
    end_of_billing_month = datetime(year, month, num_days, 23, 59, 59, tzinfo=timezone.utc)

    tickets_for_period = [
        t for t in all_tickets_this_year
        if start_of_billing_month <= datetime.fromisoformat(t.last_updated_at.replace('Z', '+00:00')) <= end_of_billing_month
    ]
    hours_for_period = sum(float(t.total_hours_spent or 0) for t in tickets_for_period)

    prepaid_monthly = 0.0
    prepaid_yearly = 0.0
    if rate_overrides:
        if rate_overrides.override_prepaid_hours_monthly_enabled:
            prepaid_monthly = float(rate_overrides.prepaid_hours_monthly or 0)
        if rate_overrides.override_prepaid_hours_yearly_enabled:
            prepaid_yearly = float(rate_overrides.prepaid_hours_yearly or 0)

    hours_used_prior = sum(
        float(t.total_hours_spent or 0) for t in all_tickets_this_year
        if datetime.fromisoformat(t.last_updated_at.replace('Z', '+00:00')) < start_of_billing_month
    )
    remaining_yearly_hours = max(0, prepaid_yearly - hours_used_prior)

    billable_hours = max(0, max(0, hours_for_period - prepaid_monthly) - remaining_yearly_hours)
    ticket_charge = billable_hours * float(effective_rates.get('per_hour_ticket_cost', 0) or 0)

    # Calculate hours for dashboard display
    now = datetime.now(timezone.utc)
    hours_this_month = sum(
        float(t.total_hours_spent or 0) for t in all_tickets_this_year
        if datetime.fromisoformat(t.last_updated_at.replace('Z', '+00:00')).month == now.month
    )
    first_day_of_current_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    last_day_of_last_month = first_day_of_current_month - timedelta(days=1)
    hours_last_month = sum(
        float(t.total_hours_spent or 0) for t in all_tickets_this_year
        if datetime.fromisoformat(t.last_updated_at.replace('Z', '+00:00')).month == last_day_of_last_month.month
    )

    # --- Calculate Backup Charges ---
    backup_info = {
        'total_backup_bytes': sum(a.get('backup_data_bytes', 0) or 0 for a in assets_data),
        'backed_up_workstations': sum(
            1 for a in assets_data
            if a.get('billing_type') == 'Workstation' and a.get('backup_data_bytes')
        ),
        'backed_up_servers': sum(
            1 for a in assets_data
            if a.get('billing_type') in ('Server', 'VM') and a.get('backup_data_bytes')
        ),
    }
    total_backup_tb = backup_info['total_backup_bytes'] / 1099511627776.0
    included_tb = (
        backup_info['backed_up_workstations'] + backup_info['backed_up_servers']
    ) * float(effective_rates.get('backup_included_tb', 1) or 1)
    overage_tb = max(0, total_backup_tb - included_tb)

    backup_base_workstation_charge = backup_info['backed_up_workstations'] * float(
        effective_rates.get('backup_base_fee_workstation', 0) or 0
    )
    backup_base_server_charge = backup_info['backed_up_servers'] * float(
        effective_rates.get('backup_base_fee_server', 0) or 0
    )
    overage_charge = overage_tb * float(effective_rates.get('backup_per_tb_fee', 0) or 0)
    backup_charge = backup_base_workstation_charge + backup_base_server_charge + overage_charge

    # --- Calculate Custom Line Item Charges ---
    billed_line_items = []
    total_line_item_charges = 0.0
    for item in custom_line_items:
        cost = 0.0
        item_type = None
        fee = 0.0

        if item.monthly_fee is not None:
            try:
                fee = float(item.monthly_fee)
                item_type = 'Recurring'
            except (ValueError, TypeError):
                fee = 0.0
        elif item.one_off_year == year and item.one_off_month == month:
            try:
                fee = float(item.one_off_fee)
                item_type = 'One-Off'
            except (ValueError, TypeError):
                fee = 0.0
        elif item.yearly_bill_month == month:
            try:
                fee = float(item.yearly_fee)
                item_type = 'Yearly'
            except (ValueError, TypeError):
                fee = 0.0

        if item_type:
            cost = fee
            total_line_item_charges += cost
            billed_line_items.append({'name': item.name, 'type': item_type, 'cost': cost})

    # --- Assemble Final Bill and Data Package ---
    total_bill = total_asset_charges + total_user_charges + ticket_charge + backup_charge + total_line_item_charges

    receipt = {
        'billed_assets': billed_assets,
        'billed_users': billed_users,
        'billed_line_items': billed_line_items,
        'total_user_charges': total_user_charges,
        'total_asset_charges': total_asset_charges,
        'total_line_item_charges': total_line_item_charges,
        'ticket_charge': ticket_charge,
        'backup_charge': backup_charge,
        'total': total_bill,
        'hours_for_billing_period': hours_for_period,
        'prepaid_hours_monthly': prepaid_monthly,
        'billable_hours': billable_hours,
        'backup_base_workstation': backup_base_workstation_charge,
        'backup_base_server': backup_base_server_charge,
        'total_included_tb': included_tb,
        'overage_tb': overage_tb,
        'overage_charge': overage_charge,
    }

    return {
        'client': company_data,
        'assets': assets_data,
        'manual_assets': [
            {'hostname': a.hostname, 'billing_type': a.billing_type, 'custom_cost': a.custom_cost}
            for a in manual_assets
        ],
        'users': users_data,
        'manual_users': [
            {'full_name': u.full_name, 'billing_type': u.billing_type, 'custom_cost': u.custom_cost}
            for u in manual_users
        ],
        'custom_line_items': [
            {'name': i.name, 'description': i.description, 'monthly_fee': i.monthly_fee,
             'one_off_fee': i.one_off_fee, 'yearly_fee': i.yearly_fee}
            for i in custom_line_items
        ],
        'tickets_for_billing_period': [
            {'ticket_number': t.ticket_number, 'subject': t.subject, 'total_hours_spent': float(t.total_hours_spent or 0)}
            for t in tickets_for_period
        ],
        'receipt_data': receipt,
        'effective_rates': effective_rates,
        'effective_features': effective_features,
        'plan_features': effective_features,  # Alias for template compatibility
        'feature_override_status': feature_override_status,
        'quantities': dict(quantities),
        'backup_info': backup_info,
        'total_backup_tb': total_backup_tb,
        'remaining_yearly_hours': remaining_yearly_hours,
        'hours_this_month': hours_this_month,
        'hours_last_month': hours_last_month,
        'support_level_display': support_level_display,
        'contract_end_date': contract_end_date,
        'contract_expired': contract_expired,
    }
