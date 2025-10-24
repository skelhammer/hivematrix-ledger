"""
RESTful API Routes for Ledger Override Management

These endpoints allow other services to programmatically manage billing overrides.
All endpoints require service-to-service authentication.

Endpoints:
- Client Billing Overrides (custom rates per company)
- Asset Billing Overrides (custom billing type per asset)
- User Billing Overrides (paid/free/custom per user)
- Manual Assets (assets not in Codex)
- Manual Users (users not in Codex)
- Custom Line Items (one-off, recurring, yearly charges)
"""

from flask import Blueprint, jsonify, request, g
from app.auth import token_required
from extensions import db
from models import (
    ClientBillingOverride, AssetBillingOverride, UserBillingOverride,
    ManualAsset, ManualUser, CustomLineItem
)

api_bp = Blueprint('api', __name__, url_prefix='/api/overrides')


# ===== CLIENT BILLING OVERRIDES =====

@api_bp.route('/client/<account_number>', methods=['GET'])
@token_required
def get_client_overrides(account_number):
    """Get all billing overrides for a specific company."""
    override = ClientBillingOverride.query.filter_by(
        company_account_number=account_number
    ).first()

    if not override:
        return jsonify({'overrides': None, 'message': 'No overrides configured'}), 200

    # Convert to dict
    data = {
        'company_account_number': override.company_account_number,
        'billing_plan': override.billing_plan if override.override_billing_plan_enabled else None,
        'support_level': override.support_level if override.override_support_level_enabled else None,
        'per_user_cost': float(override.per_user_cost) if override.override_puc_enabled and override.per_user_cost else None,
        'per_workstation_cost': float(override.per_workstation_cost) if override.override_pwc_enabled and override.per_workstation_cost else None,
        'per_server_cost': float(override.per_server_cost) if override.override_psc_enabled and override.per_server_cost else None,
        'per_vm_cost': float(override.per_vm_cost) if override.override_pvc_enabled and override.per_vm_cost else None,
        'per_switch_cost': float(override.per_switch_cost) if override.override_pswitchc_enabled and override.per_switch_cost else None,
        'per_firewall_cost': float(override.per_firewall_cost) if override.override_pfirewallc_enabled and override.per_firewall_cost else None,
        'per_hour_ticket_cost': float(override.per_hour_ticket_cost) if override.override_phtc_enabled and override.per_hour_ticket_cost else None,
        'prepaid_hours_monthly': float(override.prepaid_hours_monthly) if override.override_prepaid_hours_monthly_enabled and override.prepaid_hours_monthly else None,
        'prepaid_hours_yearly': float(override.prepaid_hours_yearly) if override.override_prepaid_hours_yearly_enabled and override.prepaid_hours_yearly else None,
    }

    return jsonify({'overrides': data}), 200


@api_bp.route('/client/<account_number>', methods=['PUT', 'POST'])
@token_required
def set_client_overrides(account_number):
    """Set or update billing overrides for a company."""
    data = request.get_json()

    if not data:
        return jsonify({'error': 'No data provided'}), 400

    # Get or create override
    override = ClientBillingOverride.query.filter_by(
        company_account_number=account_number
    ).first()

    if not override:
        override = ClientBillingOverride(company_account_number=account_number)
        db.session.add(override)

    # Update fields (only set if provided)
    if 'billing_plan' in data:
        override.override_billing_plan_enabled = True
        override.billing_plan = data['billing_plan']

    if 'support_level' in data:
        override.override_support_level_enabled = True
        override.support_level = data['support_level']

    # Rate overrides
    rate_fields = [
        ('per_user_cost', 'puc'),
        ('per_workstation_cost', 'pwc'),
        ('per_server_cost', 'psc'),
        ('per_vm_cost', 'pvc'),
        ('per_switch_cost', 'pswitchc'),
        ('per_firewall_cost', 'pfirewallc'),
        ('per_hour_ticket_cost', 'phtc'),
        ('prepaid_hours_monthly', 'prepaid_hours_monthly'),
        ('prepaid_hours_yearly', 'prepaid_hours_yearly'),
    ]

    for field_name, short_name in rate_fields:
        if field_name in data:
            setattr(override, f'override_{short_name}_enabled', True)
            setattr(override, field_name, float(data[field_name]))

    try:
        db.session.commit()
        return jsonify({'message': 'Overrides updated successfully'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@api_bp.route('/client/<account_number>', methods=['DELETE'])
@token_required
def delete_client_overrides(account_number):
    """Remove all billing overrides for a company."""
    override = ClientBillingOverride.query.filter_by(
        company_account_number=account_number
    ).first()

    if not override:
        return jsonify({'message': 'No overrides to delete'}), 200

    db.session.delete(override)
    db.session.commit()

    return jsonify({'message': 'Overrides deleted successfully'}), 200


# ===== ASSET BILLING OVERRIDES =====

@api_bp.route('/asset/<int:asset_id>', methods=['GET'])
@token_required
def get_asset_override(asset_id):
    """Get billing override for a specific asset."""
    override = AssetBillingOverride.query.filter_by(asset_id=asset_id).first()

    if not override:
        return jsonify({'override': None}), 200

    data = {
        'asset_id': override.asset_id,
        'billing_type': override.billing_type,
        'custom_cost': float(override.custom_cost) if override.custom_cost else None
    }

    return jsonify({'override': data}), 200


@api_bp.route('/asset/<int:asset_id>', methods=['PUT', 'POST'])
@token_required
def set_asset_override(asset_id):
    """Set or update billing override for an asset."""
    data = request.get_json()

    if not data or 'billing_type' not in data:
        return jsonify({'error': 'billing_type is required'}), 400

    override = AssetBillingOverride.query.filter_by(asset_id=asset_id).first()

    if not override:
        override = AssetBillingOverride(asset_id=asset_id)
        db.session.add(override)

    override.billing_type = data['billing_type']
    override.custom_cost = float(data['custom_cost']) if 'custom_cost' in data else None

    try:
        db.session.commit()
        return jsonify({'message': 'Asset override updated successfully'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@api_bp.route('/asset/<int:asset_id>', methods=['DELETE'])
@token_required
def delete_asset_override(asset_id):
    """Remove billing override for an asset."""
    override = AssetBillingOverride.query.filter_by(asset_id=asset_id).first()

    if not override:
        return jsonify({'message': 'No override to delete'}), 200

    db.session.delete(override)
    db.session.commit()

    return jsonify({'message': 'Asset override deleted successfully'}), 200


# ===== USER BILLING OVERRIDES =====

@api_bp.route('/user/<int:user_id>', methods=['GET'])
@token_required
def get_user_override(user_id):
    """Get billing override for a specific user."""
    override = UserBillingOverride.query.filter_by(user_id=user_id).first()

    if not override:
        return jsonify({'override': None}), 200

    data = {
        'user_id': override.user_id,
        'billing_type': override.billing_type,
        'custom_cost': float(override.custom_cost) if override.custom_cost else None
    }

    return jsonify({'override': data}), 200


@api_bp.route('/user/<int:user_id>', methods=['PUT', 'POST'])
@token_required
def set_user_override(user_id):
    """Set or update billing override for a user."""
    data = request.get_json()

    if not data or 'billing_type' not in data:
        return jsonify({'error': 'billing_type is required'}), 400

    override = UserBillingOverride.query.filter_by(user_id=user_id).first()

    if not override:
        override = UserBillingOverride(user_id=user_id)
        db.session.add(override)

    override.billing_type = data['billing_type']
    override.custom_cost = float(data['custom_cost']) if 'custom_cost' in data else None

    try:
        db.session.commit()
        return jsonify({'message': 'User override updated successfully'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@api_bp.route('/user/<int:user_id>', methods=['DELETE'])
@token_required
def delete_user_override(user_id):
    """Remove billing override for a user."""
    override = UserBillingOverride.query.filter_by(user_id=user_id).first()

    if not override:
        return jsonify({'message': 'No override to delete'}), 200

    db.session.delete(override)
    db.session.commit()

    return jsonify({'message': 'User override deleted successfully'}), 200


# ===== MANUAL ASSETS =====

@api_bp.route('/manual-assets/<account_number>', methods=['GET'])
@token_required
def get_manual_assets(account_number):
    """Get all manual assets for a company."""
    assets = ManualAsset.query.filter_by(company_account_number=account_number).all()

    data = [{
        'id': a.id,
        'hostname': a.hostname,
        'billing_type': a.billing_type,
        'custom_cost': float(a.custom_cost) if a.custom_cost else None,
        'notes': a.notes
    } for a in assets]

    return jsonify({'manual_assets': data}), 200


@api_bp.route('/manual-assets/<account_number>', methods=['POST'])
@token_required
def add_manual_asset(account_number):
    """Add a manual asset for a company."""
    data = request.get_json()

    if not data or 'hostname' not in data or 'billing_type' not in data:
        return jsonify({'error': 'hostname and billing_type are required'}), 400

    asset = ManualAsset(
        company_account_number=account_number,
        hostname=data['hostname'],
        billing_type=data['billing_type'],
        custom_cost=float(data['custom_cost']) if 'custom_cost' in data else None,
        notes=data.get('notes')
    )

    db.session.add(asset)

    try:
        db.session.commit()
        return jsonify({'message': 'Manual asset added', 'id': asset.id}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@api_bp.route('/manual-assets/<account_number>/<int:asset_id>', methods=['DELETE'])
@token_required
def delete_manual_asset(account_number, asset_id):
    """Delete a manual asset."""
    asset = ManualAsset.query.filter_by(
        id=asset_id,
        company_account_number=account_number
    ).first()

    if not asset:
        return jsonify({'error': 'Manual asset not found'}), 404

    db.session.delete(asset)
    db.session.commit()

    return jsonify({'message': 'Manual asset deleted'}), 200


# ===== MANUAL USERS =====

@api_bp.route('/manual-users/<account_number>', methods=['GET'])
@token_required
def get_manual_users(account_number):
    """Get all manual users for a company."""
    users = ManualUser.query.filter_by(company_account_number=account_number).all()

    data = [{
        'id': u.id,
        'full_name': u.full_name,
        'billing_type': u.billing_type,
        'custom_cost': float(u.custom_cost) if u.custom_cost else None,
        'notes': u.notes
    } for u in users]

    return jsonify({'manual_users': data}), 200


@api_bp.route('/manual-users/<account_number>', methods=['POST'])
@token_required
def add_manual_user(account_number):
    """Add a manual user for a company."""
    data = request.get_json()

    if not data or 'full_name' not in data or 'billing_type' not in data:
        return jsonify({'error': 'full_name and billing_type are required'}), 400

    user = ManualUser(
        company_account_number=account_number,
        full_name=data['full_name'],
        billing_type=data['billing_type'],
        custom_cost=float(data['custom_cost']) if 'custom_cost' in data else None,
        notes=data.get('notes')
    )

    db.session.add(user)

    try:
        db.session.commit()
        return jsonify({'message': 'Manual user added', 'id': user.id}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@api_bp.route('/manual-users/<account_number>/<int:user_id>', methods=['DELETE'])
@token_required
def delete_manual_user(account_number, user_id):
    """Delete a manual user."""
    user = ManualUser.query.filter_by(
        id=user_id,
        company_account_number=account_number
    ).first()

    if not user:
        return jsonify({'error': 'Manual user not found'}), 404

    db.session.delete(user)
    db.session.commit()

    return jsonify({'message': 'Manual user deleted'}), 200


# ===== CUSTOM LINE ITEMS =====

@api_bp.route('/line-items/<account_number>', methods=['GET'])
@token_required
def get_custom_line_items(account_number):
    """Get all custom line items for a company."""
    items = CustomLineItem.query.filter_by(company_account_number=account_number).all()

    data = [{
        'id': i.id,
        'name': i.name,
        'description': i.description,
        'monthly_fee': float(i.monthly_fee) if i.monthly_fee else None,
        'one_off_fee': float(i.one_off_fee) if i.one_off_fee else None,
        'one_off_year': i.one_off_year,
        'one_off_month': i.one_off_month,
        'yearly_fee': float(i.yearly_fee) if i.yearly_fee else None,
        'yearly_bill_month': i.yearly_bill_month
    } for i in items]

    return jsonify({'line_items': data}), 200


@api_bp.route('/line-items/<account_number>', methods=['POST'])
@token_required
def add_custom_line_item(account_number):
    """Add a custom line item for a company."""
    data = request.get_json()

    if not data or 'name' not in data:
        return jsonify({'error': 'name is required'}), 400

    item = CustomLineItem(
        company_account_number=account_number,
        name=data['name'],
        description=data.get('description'),
        monthly_fee=float(data['monthly_fee']) if 'monthly_fee' in data else None,
        one_off_fee=float(data['one_off_fee']) if 'one_off_fee' in data else None,
        one_off_year=data.get('one_off_year'),
        one_off_month=data.get('one_off_month'),
        yearly_fee=float(data['yearly_fee']) if 'yearly_fee' in data else None,
        yearly_bill_month=data.get('yearly_bill_month')
    )

    db.session.add(item)

    try:
        db.session.commit()
        return jsonify({'message': 'Custom line item added', 'id': item.id}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@api_bp.route('/line-items/<account_number>/<int:item_id>', methods=['PUT'])
@token_required
def update_custom_line_item(account_number, item_id):
    """Update a custom line item."""
    item = CustomLineItem.query.filter_by(
        id=item_id,
        company_account_number=account_number
    ).first()

    if not item:
        return jsonify({'error': 'Line item not found'}), 404

    data = request.get_json()

    if 'name' in data:
        item.name = data['name']
    if 'description' in data:
        item.description = data['description']
    if 'monthly_fee' in data:
        item.monthly_fee = float(data['monthly_fee']) if data['monthly_fee'] else None
    if 'one_off_fee' in data:
        item.one_off_fee = float(data['one_off_fee']) if data['one_off_fee'] else None
    if 'one_off_year' in data:
        item.one_off_year = data['one_off_year']
    if 'one_off_month' in data:
        item.one_off_month = data['one_off_month']
    if 'yearly_fee' in data:
        item.yearly_fee = float(data['yearly_fee']) if data['yearly_fee'] else None
    if 'yearly_bill_month' in data:
        item.yearly_bill_month = data['yearly_bill_month']

    try:
        db.session.commit()
        return jsonify({'message': 'Line item updated'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@api_bp.route('/line-items/<account_number>/<int:item_id>', methods=['DELETE'])
@token_required
def delete_custom_line_item(account_number, item_id):
    """Delete a custom line item."""
    item = CustomLineItem.query.filter_by(
        id=item_id,
        company_account_number=account_number
    ).first()

    if not item:
        return jsonify({'error': 'Line item not found'}), 404

    db.session.delete(item)
    db.session.commit()

    return jsonify({'message': 'Line item deleted'}), 200
