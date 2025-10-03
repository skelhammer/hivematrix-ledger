from extensions import db
from sqlalchemy import BigInteger

# Billing Plans - Base pricing structures
class BillingPlan(db.Model):
    __tablename__ = 'billing_plans'

    id = db.Column(db.Integer, primary_key=True)
    billing_plan = db.Column(db.String(100), nullable=False)
    term_length = db.Column(db.String(50), nullable=False)  # 'Month to Month', '1-Year', '2-Year', '3-Year'
    support_level = db.Column(db.String(100), nullable=False)  # 'Billed Hourly', 'All Inclusive', etc.

    # Per-item costs
    per_user_cost = db.Column(db.Numeric(10, 2), default=0.00)
    per_workstation_cost = db.Column(db.Numeric(10, 2), default=0.00)
    per_server_cost = db.Column(db.Numeric(10, 2), default=0.00)
    per_vm_cost = db.Column(db.Numeric(10, 2), default=0.00)
    per_switch_cost = db.Column(db.Numeric(10, 2), default=0.00)
    per_firewall_cost = db.Column(db.Numeric(10, 2), default=0.00)
    per_hour_ticket_cost = db.Column(db.Numeric(10, 2), default=0.00)

    # Backup costs
    backup_base_fee_workstation = db.Column(db.Numeric(10, 2), default=0.00)
    backup_base_fee_server = db.Column(db.Numeric(10, 2), default=0.00)
    backup_included_tb = db.Column(db.Numeric(10, 2), default=1.00)  # TB included per device
    backup_per_tb_fee = db.Column(db.Numeric(10, 2), default=0.00)  # Cost per TB over included

    # Unique constraint
    __table_args__ = (db.UniqueConstraint('billing_plan', 'term_length', name='unique_plan_term'),)


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
    company_account_number = db.Column(db.String(50), nullable=False)
    hostname = db.Column(db.String(150), nullable=False)
    billing_type = db.Column(db.String(50), nullable=False)  # 'Workstation', 'Server', etc.
    custom_cost = db.Column(db.Numeric(10, 2))  # If billing_type is 'Custom'
    notes = db.Column(db.Text)


# Manual Users - Users added manually (not from Codex/Freshservice)
class ManualUser(db.Model):
    __tablename__ = 'manual_users'

    id = db.Column(db.Integer, primary_key=True)
    company_account_number = db.Column(db.String(50), nullable=False)
    full_name = db.Column(db.String(150), nullable=False)
    billing_type = db.Column(db.String(50), nullable=False)  # 'Paid', 'Free', 'Custom'
    custom_cost = db.Column(db.Numeric(10, 2))  # If billing_type is 'Custom'
    notes = db.Column(db.Text)


# Custom Line Items - One-off, recurring, or yearly charges
class CustomLineItem(db.Model):
    __tablename__ = 'custom_line_items'

    id = db.Column(db.Integer, primary_key=True)
    company_account_number = db.Column(db.String(50), nullable=False)
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


# Feature Options - Available features to override
class FeatureOption(db.Model):
    __tablename__ = 'feature_options'

    id = db.Column(db.Integer, primary_key=True)
    feature_type = db.Column(db.String(100), nullable=False)
    display_name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text)

    # Unique constraint on combination of feature_type + display_name
    __table_args__ = (db.UniqueConstraint('feature_type', 'display_name', name='unique_feature_option'),)


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
