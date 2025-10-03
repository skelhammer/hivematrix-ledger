"""
Admin Routes for Ledger Service

Comprehensive admin functionality including:
- Billing plan management
- Feature options management
- Scheduler/puller management
- System settings
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, g, jsonify
from app.auth import admin_required
from extensions import db
from models import (
    BillingPlan, FeatureOption, SchedulerJob, ClientBillingOverride
)
from datetime import datetime
import subprocess
import sys
import os

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


# ===== BILLING PLANS =====

@admin_bp.route('/plans')
@admin_required
def plans():
    """Manage billing plans."""
    if g.is_service_call:
        return {'error': 'This endpoint is for users only'}, 403

    # Group plans by name
    all_plans = BillingPlan.query.order_by(BillingPlan.billing_plan, BillingPlan.term_length).all()

    grouped_plans = {}
    for plan in all_plans:
        if plan.billing_plan not in grouped_plans:
            grouped_plans[plan.billing_plan] = []
        grouped_plans[plan.billing_plan].append(plan)

    return render_template('admin/plans.html', user=g.user, grouped_plans=grouped_plans)


@admin_bp.route('/plans/add', methods=['POST'])
@admin_required
def add_plan():
    """Add a new billing plan."""
    try:
        plan = BillingPlan(
            billing_plan=request.form.get('billing_plan'),
            term_length=request.form.get('term_length'),
            support_level=request.form.get('support_level'),
            per_user_cost=float(request.form.get('per_user_cost', 0)),
            per_workstation_cost=float(request.form.get('per_workstation_cost', 0)),
            per_server_cost=float(request.form.get('per_server_cost', 0)),
            per_vm_cost=float(request.form.get('per_vm_cost', 0)),
            per_switch_cost=float(request.form.get('per_switch_cost', 0)),
            per_firewall_cost=float(request.form.get('per_firewall_cost', 0)),
            per_hour_ticket_cost=float(request.form.get('per_hour_ticket_cost', 0)),
            backup_base_fee_workstation=float(request.form.get('backup_base_fee_workstation', 0)),
            backup_base_fee_server=float(request.form.get('backup_base_fee_server', 0)),
            backup_included_tb=float(request.form.get('backup_included_tb', 1)),
            backup_per_tb_fee=float(request.form.get('backup_per_tb_fee', 0))
        )
        db.session.add(plan)
        db.session.commit()
        flash(f"Plan '{plan.billing_plan}' ({plan.term_length}) created successfully.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error creating plan: {e}", "error")

    return redirect(url_for('admin.plans'))


@admin_bp.route('/plans/edit/<int:plan_id>', methods=['POST'])
@admin_required
def edit_plan(plan_id):
    """Edit an existing billing plan."""
    plan = BillingPlan.query.get_or_404(plan_id)

    try:
        plan.billing_plan = request.form.get('billing_plan')
        plan.term_length = request.form.get('term_length')
        plan.support_level = request.form.get('support_level')
        plan.per_user_cost = float(request.form.get('per_user_cost', 0))
        plan.per_workstation_cost = float(request.form.get('per_workstation_cost', 0))
        plan.per_server_cost = float(request.form.get('per_server_cost', 0))
        plan.per_vm_cost = float(request.form.get('per_vm_cost', 0))
        plan.per_switch_cost = float(request.form.get('per_switch_cost', 0))
        plan.per_firewall_cost = float(request.form.get('per_firewall_cost', 0))
        plan.per_hour_ticket_cost = float(request.form.get('per_hour_ticket_cost', 0))
        plan.backup_base_fee_workstation = float(request.form.get('backup_base_fee_workstation', 0))
        plan.backup_base_fee_server = float(request.form.get('backup_base_fee_server', 0))
        plan.backup_included_tb = float(request.form.get('backup_included_tb', 1))
        plan.backup_per_tb_fee = float(request.form.get('backup_per_tb_fee', 0))

        db.session.commit()
        flash(f"Plan '{plan.billing_plan}' updated successfully.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error updating plan: {e}", "error")

    return redirect(url_for('admin.plans'))


@admin_bp.route('/plans/delete/<int:plan_id>', methods=['POST'])
@admin_required
def delete_plan(plan_id):
    """Delete a billing plan."""
    plan = BillingPlan.query.get_or_404(plan_id)

    # Check if any clients are using this plan
    overrides_count = ClientBillingOverride.query.filter_by(billing_plan=plan.billing_plan).count()

    if overrides_count > 0:
        flash(f"Cannot delete plan '{plan.billing_plan}'. {overrides_count} client(s) have overrides using this plan.", "error")
        return redirect(url_for('admin.plans'))

    try:
        db.session.delete(plan)
        db.session.commit()
        flash(f"Plan '{plan.billing_plan}' ({plan.term_length}) deleted successfully.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error deleting plan: {e}", "error")

    return redirect(url_for('admin.plans'))


# ===== FEATURE OPTIONS =====

@admin_bp.route('/features')
@admin_required
def features():
    """Manage feature options."""
    if g.is_service_call:
        return {'error': 'This endpoint is for users only'}, 403

    feature_options = FeatureOption.query.order_by(FeatureOption.feature_type, FeatureOption.display_name).all()

    # Group by feature type
    grouped_features = {}
    for option in feature_options:
        if option.feature_type not in grouped_features:
            grouped_features[option.feature_type] = []
        grouped_features[option.feature_type].append(option)

    return render_template('admin/features.html', user=g.user, grouped_features=grouped_features)


@admin_bp.route('/features/add', methods=['POST'])
@admin_required
def add_feature():
    """Add a new feature option."""
    try:
        feature = FeatureOption(
            feature_type=request.form.get('feature_type'),
            display_name=request.form.get('display_name'),
            description=request.form.get('description')
        )
        db.session.add(feature)
        db.session.commit()
        flash(f"Feature '{feature.display_name}' added successfully.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error adding feature: {e}", "error")

    return redirect(url_for('admin.features'))


@admin_bp.route('/features/edit/<int:feature_id>', methods=['POST'])
@admin_required
def edit_feature(feature_id):
    """Edit a feature option."""
    feature = FeatureOption.query.get_or_404(feature_id)

    try:
        feature.feature_type = request.form.get('feature_type')
        feature.display_name = request.form.get('display_name')
        feature.description = request.form.get('description')
        db.session.commit()
        flash(f"Feature '{feature.display_name}' updated successfully.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error updating feature: {e}", "error")

    return redirect(url_for('admin.features'))


@admin_bp.route('/features/delete/<int:feature_id>', methods=['POST'])
@admin_required
def delete_feature(feature_id):
    """Delete a feature option."""
    feature = FeatureOption.query.get_or_404(feature_id)

    try:
        db.session.delete(feature)
        db.session.commit()
        flash(f"Feature '{feature.display_name}' deleted successfully.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error deleting feature: {e}", "error")

    return redirect(url_for('admin.features'))


# ===== SCHEDULER / PULLERS =====

@admin_bp.route('/pullers')
@admin_required
def pullers():
    """Manage data pullers and sync jobs."""
    if g.is_service_call:
        return {'error': 'This endpoint is for users only'}, 403

    jobs = SchedulerJob.query.order_by(SchedulerJob.job_name).all()

    return render_template('admin/pullers.html', user=g.user, jobs=jobs)


@admin_bp.route('/pullers/add', methods=['POST'])
@admin_required
def add_puller():
    """Add a new scheduler job."""
    try:
        job = SchedulerJob(
            job_name=request.form.get('job_name'),
            script_path=request.form.get('script_path'),
            schedule_cron=request.form.get('schedule_cron'),
            description=request.form.get('description'),
            enabled=request.form.get('enabled') == 'on'
        )
        db.session.add(job)
        db.session.commit()
        flash(f"Puller '{job.job_name}' added successfully.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error adding puller: {e}", "error")

    return redirect(url_for('admin.pullers'))


@admin_bp.route('/pullers/edit/<int:job_id>', methods=['POST'])
@admin_required
def edit_puller(job_id):
    """Edit a scheduler job."""
    job = SchedulerJob.query.get_or_404(job_id)

    try:
        job.job_name = request.form.get('job_name')
        job.script_path = request.form.get('script_path')
        job.schedule_cron = request.form.get('schedule_cron')
        job.description = request.form.get('description')
        job.enabled = request.form.get('enabled') == 'on'
        db.session.commit()
        flash(f"Puller '{job.job_name}' updated successfully.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error updating puller: {e}", "error")

    return redirect(url_for('admin.pullers'))


@admin_bp.route('/pullers/delete/<int:job_id>', methods=['POST'])
@admin_required
def delete_puller(job_id):
    """Delete a scheduler job."""
    job = SchedulerJob.query.get_or_404(job_id)

    try:
        db.session.delete(job)
        db.session.commit()
        flash(f"Puller '{job.job_name}' deleted successfully.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error deleting puller: {e}", "error")

    return redirect(url_for('admin.pullers'))


@admin_bp.route('/pullers/run/<int:job_id>', methods=['POST'])
@admin_required
def run_puller(job_id):
    """Manually run a puller job."""
    job = SchedulerJob.query.get_or_404(job_id)

    # Update status to running
    job.last_status = 'Running'
    job.last_run = datetime.now().isoformat()
    db.session.commit()

    try:
        # Run the script as a subprocess
        python_executable = sys.executable
        result = subprocess.run(
            [python_executable, job.script_path],
            capture_output=True,
            text=True,
            check=False,
            timeout=7200,  # 2 hour timeout
            encoding='utf-8',
            errors='replace'
        )

        log_output = f"--- STDOUT ---\n{result.stdout}\n\n--- STDERR ---\n{result.stderr}"
        status = "Success" if result.returncode == 0 else "Failure"

        job.last_status = status
        job.last_run_log = log_output
        db.session.commit()

        flash(f"Puller '{job.job_name}' completed with status: {status}",
              "success" if status == "Success" else "error")
    except subprocess.TimeoutExpired:
        job.last_status = 'Timeout'
        job.last_run_log = 'Script execution timed out after 2 hours'
        db.session.commit()
        flash(f"Puller '{job.job_name}' timed out.", "error")
    except Exception as e:
        job.last_status = 'Error'
        job.last_run_log = f"Error running script: {str(e)}"
        db.session.commit()
        flash(f"Error running puller: {e}", "error")

    return redirect(url_for('admin.pullers'))


@admin_bp.route('/pullers/log/<int:job_id>')
@admin_required
def view_puller_log(job_id):
    """View the log output from a puller job."""
    if g.is_service_call:
        return {'error': 'This endpoint is for users only'}, 403

    job = SchedulerJob.query.get_or_404(job_id)
    return render_template('admin/puller_log.html', user=g.user, job=job)


# ===== SETTINGS =====

@admin_bp.route('/settings')
@admin_required
def settings():
    """Admin settings page - central hub for all admin functions."""
    if g.is_service_call:
        return {'error': 'This endpoint is for users only'}, 403

    # Get summary stats
    plans_count = BillingPlan.query.count()
    features_count = FeatureOption.query.count()
    jobs_count = SchedulerJob.query.count()

    # Get recent puller runs
    recent_jobs = SchedulerJob.query.order_by(SchedulerJob.last_run.desc()).limit(5).all()

    return render_template('admin/settings.html',
        user=g.user,
        plans_count=plans_count,
        features_count=features_count,
        jobs_count=jobs_count,
        recent_jobs=recent_jobs
    )
