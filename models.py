from extensions import db
from sqlalchemy import BigInteger

# NOTE: BillingPlan and FeatureOption models REMOVED
# These are now fetched from Codex via API (see app/codex_client.py)
# Ledger only stores local overrides and operational data

# Client Billing Overrides - Per-client custom rates
class ClientBillingOverride(db.Model):
    __tablename__ = 'client_billing_overrides'

    id = db.Column(db.Integer, primary_key=True)
    company_account_number = db.Column(db.String(50), unique=True, nullable=False)

    # Plan override
    override_billing_plan_enabled = db.Column(db.Boolean, default=False)
    billing_plan = db.Column(db.String(100))

    # Support level override
    override_support_level_enabled = db.Column(db.Boolean, default=False)
    support_level = db.Column(db.String(100))

    # Per-item cost overrides
    override_puc_enabled = db.Column(db.Boolean, default=False)
    per_user_cost = db.Column(db.Numeric(10, 2))

    override_pwc_enabled = db.Column(db.Boolean, default=False)
    per_workstation_cost = db.Column(db.Numeric(10, 2))

    override_psc_enabled = db.Column(db.Boolean, default=False)
    per_server_cost = db.Column(db.Numeric(10, 2))

    override_pvc_enabled = db.Column(db.Boolean, default=False)
    per_vm_cost = db.Column(db.Numeric(10, 2))

    override_pswitchc_enabled = db.Column(db.Boolean, default=False)
    per_switch_cost = db.Column(db.Numeric(10, 2))

    override_pfirewallc_enabled = db.Column(db.Boolean, default=False)
    per_firewall_cost = db.Column(db.Numeric(10, 2))

    override_phtc_enabled = db.Column(db.Boolean, default=False)
    per_hour_ticket_cost = db.Column(db.Numeric(10, 2))

    # Backup cost overrides
    override_bbfw_enabled = db.Column(db.Boolean, default=False)
    backup_base_fee_workstation = db.Column(db.Numeric(10, 2))

    override_bbfs_enabled = db.Column(db.Boolean, default=False)
    backup_base_fee_server = db.Column(db.Numeric(10, 2))

    override_bit_enabled = db.Column(db.Boolean, default=False)
    backup_included_tb = db.Column(db.Numeric(10, 2))

    override_bpt_enabled = db.Column(db.Boolean, default=False)
    backup_per_tb_fee = db.Column(db.Numeric(10, 2))

    # Prepaid hours
    override_prepaid_hours_monthly_enabled = db.Column(db.Boolean, default=False)
    prepaid_hours_monthly = db.Column(db.Numeric(10, 2))

    override_prepaid_hours_yearly_enabled = db.Column(db.Boolean, default=False)
    prepaid_hours_yearly = db.Column(db.Numeric(10, 2))


# Asset Billing Overrides - Override billing type for specific assets
class AssetBillingOverride(db.Model):
    __tablename__ = 'asset_billing_overrides'

    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(db.Integer, nullable=False, unique=True)  # ID from Codex
    billing_type = db.Column(db.String(50))  # 'Workstation', 'Server', 'VM', 'Switch', 'Firewall', 'Custom', 'No Charge'
    custom_cost = db.Column(db.Numeric(10, 2))  # If billing_type is 'Custom'


# User Billing Overrides - Override billing type for specific users
class UserBillingOverride(db.Model):
    __tablename__ = 'user_billing_overrides'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False, unique=True)  # ID from Codex
    billing_type = db.Column(db.String(50))  # 'Paid', 'Free', 'Custom'
    custom_cost = db.Column(db.Numeric(10, 2))  # If billing_type is 'Custom'


# Manual Assets - Assets added manually (not from Codex/Datto)
class ManualAsset(db.Model):
    __tablename__ = 'manual_assets'

    id = db.Column(db.Integer, primary_key=True)
    company_account_number = db.Column(db.String(50), nullable=False, index=True)
    hostname = db.Column(db.String(150), nullable=False)
    billing_type = db.Column(db.String(50), nullable=False)  # 'Workstation', 'Server', etc.
    custom_cost = db.Column(db.Numeric(10, 2))  # If billing_type is 'Custom'
    notes = db.Column(db.Text)


# Manual Users - Users added manually (not from Codex/PSA)
class ManualUser(db.Model):
    __tablename__ = 'manual_users'

    id = db.Column(db.Integer, primary_key=True)
    company_account_number = db.Column(db.String(50), nullable=False, index=True)
    full_name = db.Column(db.String(150), nullable=False)
    billing_type = db.Column(db.String(50), nullable=False)  # 'Paid', 'Free', 'Custom'
    custom_cost = db.Column(db.Numeric(10, 2))  # If billing_type is 'Custom'
    notes = db.Column(db.Text)


# Custom Line Items - One-off, recurring, or yearly charges
class CustomLineItem(db.Model):
    __tablename__ = 'custom_line_items'

    id = db.Column(db.Integer, primary_key=True)
    company_account_number = db.Column(db.String(50), nullable=False, index=True)
    name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text)

    # Recurring monthly fee
    monthly_fee = db.Column(db.Numeric(10, 2))

    # One-off fee (specific month/year)
    one_off_fee = db.Column(db.Numeric(10, 2))
    one_off_year = db.Column(db.Integer)
    one_off_month = db.Column(db.Integer)

    # Yearly fee (billed specific month each year)
    yearly_fee = db.Column(db.Numeric(10, 2))
    yearly_bill_month = db.Column(db.Integer)  # 1-12


# Ticket Details - Ticket hours for billing calculations
class TicketDetail(db.Model):
    __tablename__ = 'ticket_details'

    id = db.Column(db.Integer, primary_key=True)
    company_account_number = db.Column(db.String(50), nullable=False)
    ticket_id = db.Column(BigInteger, unique=True, nullable=False)
    ticket_number = db.Column(db.String(50))
    subject = db.Column(db.String(255))
    status = db.Column(db.String(50))
    priority = db.Column(db.String(50))
    total_hours_spent = db.Column(db.Numeric(10, 2), default=0.00)
    created_at = db.Column(db.String(100))
    last_updated_at = db.Column(db.String(100), nullable=False)

    # Index for fast year/month filtering
    __table_args__ = (db.Index('idx_ticket_updated', 'last_updated_at'),)


# NOTE: FeatureOption model REMOVED - now fetched from Codex via API

# Client Feature Overrides - Custom feature pricing per client
class ClientFeatureOverride(db.Model):
    __tablename__ = 'client_feature_overrides'

    id = db.Column(db.Integer, primary_key=True)
    company_account_number = db.Column(db.String(50), nullable=False)
    feature_type = db.Column(db.String(100), nullable=False)
    override_enabled = db.Column(db.Boolean, default=False)
    value = db.Column(db.String(100))

    __table_args__ = (db.UniqueConstraint('company_account_number', 'feature_type', name='unique_client_feature'),)


# Scheduler Jobs - Automated sync tasks
class SchedulerJob(db.Model):
    __tablename__ = 'scheduler_jobs'

    id = db.Column(db.Integer, primary_key=True)
    job_name = db.Column(db.String(150), nullable=False, unique=True)
    script_path = db.Column(db.String(255), nullable=False)
    schedule_cron = db.Column(db.String(100))  # Cron expression
    enabled = db.Column(db.Boolean, default=True)
    last_run = db.Column(db.String(100))  # ISO timestamp
    last_status = db.Column(db.String(50))  # 'Success', 'Failure', 'Running'
    last_run_log = db.Column(db.Text)  # Output from last run
    description = db.Column(db.Text)


# ===== ARCHIVE MODELS (Merged from hivematrix-archive) =====
# These models store immutable billing snapshots for historical record-keeping

from sqlalchemy import Index


class BillingSnapshot(db.Model):
    """
    A complete billing snapshot for a company for a specific period.
    This is the primary archive record - IMMUTABLE after creation.
    """
    __tablename__ = 'billing_snapshots'

    id = db.Column(db.Integer, primary_key=True)

    # Identification
    company_account_number = db.Column(db.String(50), nullable=False, index=True)
    company_name = db.Column(db.String(150), nullable=False)
    invoice_number = db.Column(db.String(50), unique=True, nullable=False, index=True)

    # Billing Period
    billing_year = db.Column(db.Integer, nullable=False, index=True)
    billing_month = db.Column(db.Integer, nullable=False, index=True)

    # Dates
    invoice_date = db.Column(db.String(50), nullable=False)  # When invoice was generated
    due_date = db.Column(db.String(50))  # Payment due date
    archived_at = db.Column(db.String(50), nullable=False)  # When snapshot was created

    # Billing Plan Info (at time of snapshot)
    billing_plan = db.Column(db.String(100))
    contract_term = db.Column(db.String(50))
    support_level = db.Column(db.String(100))

    # Totals
    total_amount = db.Column(db.Numeric(10, 2), nullable=False)
    total_user_charges = db.Column(db.Numeric(10, 2), default=0.00)
    total_asset_charges = db.Column(db.Numeric(10, 2), default=0.00)
    total_backup_charges = db.Column(db.Numeric(10, 2), default=0.00)
    total_ticket_charges = db.Column(db.Numeric(10, 2), default=0.00)
    total_line_item_charges = db.Column(db.Numeric(10, 2), default=0.00)

    # Counts
    user_count = db.Column(db.Integer, default=0)
    asset_count = db.Column(db.Integer, default=0)
    billable_hours = db.Column(db.Numeric(10, 2), default=0.00)

    # Complete Billing Data (JSON)
    # This stores the ENTIRE billing calculation result from Ledger
    billing_data_json = db.Column(db.Text, nullable=False)  # JSON blob

    # CSV Invoice (stored for download)
    invoice_csv = db.Column(db.Text, nullable=False)

    # Metadata
    created_by = db.Column(db.String(100))  # User or 'auto-scheduler'
    notes = db.Column(db.Text)  # Optional notes about this snapshot

    # Indexes for common queries
    __table_args__ = (
        Index('idx_company_period', 'company_account_number', 'billing_year', 'billing_month'),
        Index('idx_archived_at', 'archived_at'),
    )


class SnapshotLineItem(db.Model):
    """
    Individual line items from a billing snapshot.
    Denormalized for easier searching and reporting.
    """
    __tablename__ = 'snapshot_line_items'

    id = db.Column(db.Integer, primary_key=True)
    snapshot_id = db.Column(db.Integer, db.ForeignKey('billing_snapshots.id'), nullable=False, index=True)

    # Line Item Details
    line_type = db.Column(db.String(50), nullable=False)  # 'user', 'asset', 'backup', 'ticket', 'custom'
    item_name = db.Column(db.String(255), nullable=False)  # User/Asset name or custom item name
    description = db.Column(db.Text)  # Full description
    quantity = db.Column(db.Numeric(10, 2), default=1.00)
    rate = db.Column(db.Numeric(10, 2), nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)

    # Relationship
    snapshot = db.relationship('BillingSnapshot', backref=db.backref('line_items', lazy='dynamic'))


class ScheduledSnapshot(db.Model):
    """
    Configuration for automated snapshot creation.
    Typically runs on the 1st of each month to archive previous month.
    """
    __tablename__ = 'scheduled_snapshots'

    id = db.Column(db.Integer, primary_key=True)

    # Schedule Configuration
    enabled = db.Column(db.Boolean, default=True, nullable=False)
    day_of_month = db.Column(db.Integer, default=1, nullable=False)  # 1-31
    hour = db.Column(db.Integer, default=2, nullable=False)  # 0-23 (2am default)

    # What to snapshot
    snapshot_previous_month = db.Column(db.Boolean, default=True)  # Archive last month's bills
    snapshot_all_companies = db.Column(db.Boolean, default=True)  # All companies or specific?

    # Last Run
    last_run_at = db.Column(db.String(50))
    last_run_status = db.Column(db.String(50))  # 'success', 'partial', 'failed'
    last_run_count = db.Column(db.Integer, default=0)  # How many snapshots created
    last_run_log = db.Column(db.Text)  # Output/errors from last run

    # Metadata
    created_at = db.Column(db.String(50), nullable=False)
    updated_at = db.Column(db.String(50))


class SnapshotJob(db.Model):
    """
    Tracks individual snapshot creation jobs (manual or scheduled).
    """
    __tablename__ = 'snapshot_jobs'

    id = db.Column(db.String(50), primary_key=True)  # UUID
    job_type = db.Column(db.String(50), nullable=False)  # 'manual', 'scheduled', 'bulk'
    status = db.Column(db.String(20), nullable=False)  # 'running', 'completed', 'failed'

    # What's being snapshotted
    target_year = db.Column(db.Integer, nullable=False)
    target_month = db.Column(db.Integer, nullable=False)
    target_account_numbers = db.Column(db.Text)  # JSON array, null = all companies

    # Progress
    total_companies = db.Column(db.Integer, default=0)
    completed_companies = db.Column(db.Integer, default=0)
    failed_companies = db.Column(db.Integer, default=0)

    # Timing
    started_at = db.Column(db.String(50), nullable=False)
    completed_at = db.Column(db.String(50))

    # Output
    output = db.Column(db.Text)  # JSON output with success/failure details
    error = db.Column(db.Text)  # Error message if failed
    success = db.Column(db.Boolean)  # Overall success status

    # Who triggered it
    triggered_by = db.Column(db.String(100))  # Username or 'scheduler'
