"""
Admin Routes for Ledger Service

Admin functionality for:
- Scheduler/puller management
- System settings

NOTE: Billing plans and features are now managed in Codex, not Ledger.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, g, jsonify
from app.auth import admin_required
from extensions import db
from models import SchedulerJob, ClientBillingOverride
from datetime import datetime
import subprocess
import sys
import os

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


# NOTE: Billing plans and features management REMOVED
# These are now managed in Codex only
# Redirect users to Codex for billing plan and feature management

@admin_bp.route('/plans')
@admin_required
def plans():
    """Redirect to Codex for billing plan management."""
    flash("Billing plans are now managed in Codex. Please use Codex to manage billing plans.", "info")
    return redirect('/codex/billing-plans')


@admin_bp.route('/features')
@admin_required
def features():
    """Redirect to Codex for feature management."""
    flash("Feature options are now managed in Codex. Please use Codex to manage features.", "info")
    return redirect('/codex/billing-plans')


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
    # Note: Billing plans and features are now in Codex, not Ledger
    from app.codex_client import CodexBillingClient
    plans = CodexBillingClient.get_all_plans()
    feature_options = CodexBillingClient.get_feature_options()

    plans_count = len(plans)
    features_count = sum(len(opts) for opts in feature_options.values())
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
