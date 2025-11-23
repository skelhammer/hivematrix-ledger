"""
Archive Routes (Merged from hivematrix-archive)

Provides:
1. Historical bill search and retrieval
2. Archived snapshot viewing
3. CSV download for archived bills
4. Scheduled snapshot configuration
"""

from flask import Blueprint, render_template, g, jsonify, request, Response
from app.auth import token_required, admin_required
from extensions import db
from models import BillingSnapshot, SnapshotLineItem, SnapshotJob, ScheduledSnapshot
from datetime import datetime
import json

archive_bp = Blueprint('archive', __name__, url_prefix='/archive')


@archive_bp.route('/')
@token_required
def index():
    """Archive dashboard - shows recent snapshots and search."""
    if g.is_service_call:
        return {'error': 'This endpoint is for users only'}, 403

    # Get recent snapshots
    recent = BillingSnapshot.query.order_by(BillingSnapshot.archived_at.desc()).limit(20).all()

    # Get summary stats
    total_snapshots = BillingSnapshot.query.count()
    total_companies = db.session.query(BillingSnapshot.company_account_number).distinct().count()

    return render_template('archive/index.html',
        user=g.user,
        recent_snapshots=recent,
        total_snapshots=total_snapshots,
        total_companies=total_companies
    )


# ===== SNAPSHOT API ENDPOINTS =====

@archive_bp.route('/api/snapshot/<invoice_number>', methods=['GET'])
@token_required
def get_snapshot(invoice_number):
    """Retrieve a specific snapshot by invoice number."""
    snapshot = BillingSnapshot.query.filter_by(invoice_number=invoice_number).first()

    if not snapshot:
        return jsonify({'error': 'Snapshot not found'}), 404

    # Return snapshot data
    data = {
        'id': snapshot.id,
        'company_account_number': snapshot.company_account_number,
        'company_name': snapshot.company_name,
        'invoice_number': snapshot.invoice_number,
        'billing_year': snapshot.billing_year,
        'billing_month': snapshot.billing_month,
        'invoice_date': snapshot.invoice_date,
        'due_date': snapshot.due_date,
        'archived_at': snapshot.archived_at,
        'billing_plan': snapshot.billing_plan,
        'contract_term': snapshot.contract_term,
        'support_level': snapshot.support_level,
        'total_amount': float(snapshot.total_amount),
        'total_user_charges': float(snapshot.total_user_charges),
        'total_asset_charges': float(snapshot.total_asset_charges),
        'total_backup_charges': float(snapshot.total_backup_charges),
        'total_ticket_charges': float(snapshot.total_ticket_charges),
        'total_line_item_charges': float(snapshot.total_line_item_charges),
        'user_count': snapshot.user_count,
        'asset_count': snapshot.asset_count,
        'billable_hours': float(snapshot.billable_hours),
        'billing_data': json.loads(snapshot.billing_data_json),
        'created_by': snapshot.created_by,
        'notes': snapshot.notes
    }

    return jsonify(data), 200


@archive_bp.route('/api/snapshot/<invoice_number>/csv', methods=['GET'])
@token_required
def download_snapshot_csv(invoice_number):
    """Download the CSV invoice for a snapshot."""
    snapshot = BillingSnapshot.query.filter_by(invoice_number=invoice_number).first()

    if not snapshot:
        return jsonify({'error': 'Snapshot not found'}), 404

    # Sanitize company name for filename
    safe_name = "".join(
        c for c in snapshot.company_name if c.isalnum() or c in (' ', '_', '-')
    ).strip().replace(' ', '_')

    filename = f"{safe_name}_{snapshot.billing_year}-{snapshot.billing_month:02d}.csv"

    return Response(
        snapshot.invoice_csv,
        mimetype='text/csv',
        headers={
            'Content-Disposition': f'attachment; filename="{filename}"'
        }
    )


@archive_bp.route('/api/snapshots/search', methods=['GET'])
@token_required
def search_snapshots():
    """
    Search archived snapshots with filters.

    Query params:
    - account_number: Filter by company
    - year: Filter by billing year
    - month: Filter by billing month
    - from_date: Filter snapshots archived after this date (YYYY-MM-DD)
    - to_date: Filter snapshots archived before this date (YYYY-MM-DD)
    - limit: Max results (default 100)
    - offset: Pagination offset
    """
    query = BillingSnapshot.query

    # Apply filters
    if request.args.get('account_number'):
        query = query.filter_by(company_account_number=request.args.get('account_number'))

    if request.args.get('year'):
        query = query.filter_by(billing_year=int(request.args.get('year')))

    if request.args.get('month'):
        query = query.filter_by(billing_month=int(request.args.get('month')))

    if request.args.get('from_date'):
        query = query.filter(BillingSnapshot.archived_at >= request.args.get('from_date'))

    if request.args.get('to_date'):
        query = query.filter(BillingSnapshot.archived_at <= request.args.get('to_date'))

    # Pagination
    limit = min(int(request.args.get('limit', 100)), 1000)
    offset = int(request.args.get('offset', 0))

    # Order by most recent first
    query = query.order_by(BillingSnapshot.archived_at.desc())

    # Get total count
    total = query.count()

    # Get results
    snapshots = query.limit(limit).offset(offset).all()

    # Build response
    results = [{
        'id': s.id,
        'company_account_number': s.company_account_number,
        'company_name': s.company_name,
        'invoice_number': s.invoice_number,
        'billing_year': s.billing_year,
        'billing_month': s.billing_month,
        'invoice_date': s.invoice_date,
        'archived_at': s.archived_at,
        'total_amount': float(s.total_amount),
        'user_count': s.user_count,
        'asset_count': s.asset_count
    } for s in snapshots]

    return jsonify({
        'total': total,
        'limit': limit,
        'offset': offset,
        'results': results
    }), 200


@archive_bp.route('/api/snapshots/company/<account_number>', methods=['GET'])
@token_required
def get_company_snapshots(account_number):
    """Get all snapshots for a specific company, ordered by date."""
    snapshots = BillingSnapshot.query.filter_by(
        company_account_number=account_number
    ).order_by(
        BillingSnapshot.billing_year.desc(),
        BillingSnapshot.billing_month.desc()
    ).all()

    results = [{
        'id': s.id,
        'invoice_number': s.invoice_number,
        'billing_year': s.billing_year,
        'billing_month': s.billing_month,
        'invoice_date': s.invoice_date,
        'archived_at': s.archived_at,
        'total_amount': float(s.total_amount),
        'billing_plan': s.billing_plan,
        'contract_term': s.contract_term
    } for s in snapshots]

    return jsonify({
        'company_account_number': account_number,
        'company_name': snapshots[0].company_name if snapshots else None,
        'total_snapshots': len(snapshots),
        'snapshots': results
    }), 200


# ===== SCHEDULED SNAPSHOT CONFIGURATION =====

@archive_bp.route('/api/scheduler/config', methods=['GET', 'POST'])
@admin_required
def scheduler_config():
    """Get or update scheduled snapshot configuration."""
    if request.method == 'GET':
        config = ScheduledSnapshot.query.first()
        if not config:
            return jsonify({'config': None}), 200

        return jsonify({
            'config': {
                'id': config.id,
                'enabled': config.enabled,
                'day_of_month': config.day_of_month,
                'hour': config.hour,
                'snapshot_previous_month': config.snapshot_previous_month,
                'snapshot_all_companies': config.snapshot_all_companies,
                'last_run_at': config.last_run_at,
                'last_run_status': config.last_run_status,
                'last_run_count': config.last_run_count
            }
        }), 200

    # POST - update config
    data = request.get_json()
    config = ScheduledSnapshot.query.first()

    if not config:
        config = ScheduledSnapshot(created_at=datetime.now().isoformat())
        db.session.add(config)

    if 'enabled' in data:
        config.enabled = data['enabled']
    if 'day_of_month' in data:
        config.day_of_month = int(data['day_of_month'])
    if 'hour' in data:
        config.hour = int(data['hour'])
    if 'snapshot_previous_month' in data:
        config.snapshot_previous_month = data['snapshot_previous_month']
    if 'snapshot_all_companies' in data:
        config.snapshot_all_companies = data['snapshot_all_companies']

    config.updated_at = datetime.now().isoformat()

    try:
        db.session.commit()
        return jsonify({'message': 'Scheduler configuration updated'}), 200
    except Exception as e:
        db.session.rollback()
        from app.helm_logger import get_helm_logger
        logger = get_helm_logger()
        if logger:
            logger.error(f"Failed to update scheduler configuration: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500


@archive_bp.route('/api/scheduler/jobs', methods=['GET'])
@token_required
def list_scheduler_jobs():
    """Get list of snapshot jobs."""
    limit = min(int(request.args.get('limit', 50)), 100)
    offset = int(request.args.get('offset', 0))

    jobs = SnapshotJob.query.order_by(SnapshotJob.started_at.desc()).limit(limit).offset(offset).all()

    results = []
    for job in jobs:
        output = json.loads(job.output) if job.output else {}
        results.append({
            'id': job.id,
            'job_type': job.job_type,
            'status': job.status,
            'target_year': job.target_year,
            'target_month': job.target_month,
            'total_companies': job.total_companies,
            'completed_companies': job.completed_companies,
            'started_at': job.started_at,
            'completed_at': job.completed_at,
            'success': job.success,
            'triggered_by': job.triggered_by,
            'success_count': output.get('success_count'),
            'failed_count': output.get('failed_count')
        })

    return jsonify({'jobs': results}), 200


@archive_bp.route('/api/scheduler/jobs/<job_id>', methods=['GET'])
@token_required
def get_job_status(job_id):
    """Get detailed status of a specific job."""
    job = SnapshotJob.query.get(job_id)

    if not job:
        return jsonify({'error': 'Job not found'}), 404

    output = json.loads(job.output) if job.output else {}

    job_data = {
        'id': job.id,
        'job_type': job.job_type,
        'status': job.status,
        'target_year': job.target_year,
        'target_month': job.target_month,
        'total_companies': job.total_companies,
        'completed_companies': job.completed_companies,
        'started_at': job.started_at,
        'completed_at': job.completed_at,
        'success': job.success,
        'triggered_by': job.triggered_by,
        'output': output,
        'error': job.error
    }

    return jsonify(job_data), 200
