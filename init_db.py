import os
import sys
import configparser
from getpass import getpass
from sqlalchemy import create_engine
from dotenv import load_dotenv

load_dotenv('.flaskenv')
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app
from extensions import db
from models import (
    BillingPlan, ClientBillingOverride, AssetBillingOverride, UserBillingOverride,
    ManualAsset, ManualUser, CustomLineItem, TicketDetail, FeatureOption, ClientFeatureOverride,
    SchedulerJob
)


def get_db_credentials(config):
    """Prompts the user for PostgreSQL connection details."""
    print("\n--- PostgreSQL Database Configuration ---")

    # Load existing or use defaults
    db_details = {
        'host': config.get('database_credentials', 'db_host', fallback='localhost'),
        'port': config.get('database_credentials', 'db_port', fallback='5432'),
        'user': config.get('database_credentials', 'db_user', fallback='ledger_user'),
        'dbname': config.get('database_credentials', 'db_dbname', fallback='ledger_db')
    }

    host = input(f"Host [{db_details['host']}]: ") or db_details['host']
    port = input(f"Port [{db_details['port']}]: ") or db_details['port']
    dbname = input(f"Database Name [{db_details['dbname']}]: ") or db_details['dbname']
    user = input(f"User [{db_details['user']}]: ") or db_details['user']

    # Try to get password from config first (won't be stored, but helpful for re-runs in same session)
    password = getpass("Password: ")

    return {'host': host, 'port': port, 'dbname': dbname, 'user': user, 'password': password}


def test_db_connection(creds):
    """Tests the database connection."""
    from urllib.parse import quote_plus

    escaped_password = quote_plus(creds['password'])
    conn_string = f"postgresql://{creds['user']}:{escaped_password}@{creds['host']}:{creds['port']}/{creds['dbname']}"

    try:
        engine = create_engine(conn_string)
        with engine.connect() as connection:
            print("\n✓ Database connection successful!")
            return conn_string, True
    except Exception as e:
        print(f"\n✗ Connection failed: {e}", file=sys.stderr)
        return None, False


def create_sample_billing_plans():
    """Creates comprehensive billing plans matching production setup."""
    print("\n--- Creating Billing Plans ---")

    # Plan names from your config
    plan_names = ['[PLAN-D]', '[PLAN-C]', '[PLAN-B]', '[PLAN-A]',
                  '[PLAN-E]', 'MSP Hybrid', '[PLAN-F]', '[PLAN-G]', 'Break Fix']

    term_lengths = ['Month to Month', '1-Year', '2-Year', '3-Year']

    # Base pricing structure (can be customized per plan)
    base_pricing = {
        'per_user_cost': 15.00,
        'per_workstation_cost': 50.00,
        'per_server_cost': 150.00,
        'per_vm_cost': 100.00,
        'per_switch_cost': 25.00,
        'per_firewall_cost': 75.00,
        'per_hour_ticket_cost': 150.00,
        'backup_base_fee_workstation': 5.00,
        'backup_base_fee_server': 20.00,
        'backup_included_tb': 1.0,
        'backup_per_tb_fee': 10.00
    }

    # Support level mapping
    support_levels = {
        '[PLAN-D]': 'Hourly',
        '[PLAN-C]': 'Hourly',
        '[PLAN-B]': 'Unlimited',
        '[PLAN-A]': 'Unlimited',
        '[PLAN-E]': 'Unlimited',
        'MSP Hybrid': 'Unlimited',
        '[PLAN-F]': 'Hourly',
        '[PLAN-G]': 'Hourly',
        'Break Fix': 'Hourly'
    }

    created_count = 0
    existing_count = 0

    for plan_name in plan_names:
        support_level = support_levels.get(plan_name, 'Hourly')

        for term_length in term_lengths:
            # Check if exists
            existing = BillingPlan.query.filter_by(
                billing_plan=plan_name,
                term_length=term_length
            ).first()

            if not existing:
                # Create new plan
                plan = BillingPlan(
                    billing_plan=plan_name,
                    term_length=term_length,
                    support_level=support_level,
                    **base_pricing
                )
                db.session.add(plan)
                created_count += 1
            else:
                existing_count += 1

    db.session.commit()
    print(f"  ✓ Created {created_count} plans, {existing_count} already existed")
    print("✓ Billing plans setup complete!")


def create_feature_options():
    """Creates feature options matching production setup."""
    print("\n--- Creating Feature Options ---")

    # Features from your config
    features = {
        'antivirus': ['Datto EDR', 'SentinelOne', 'Not Included'],
        'email_security': ['ProofPoint', 'Not Included'],
        'network_management': ['Auvik', 'Not Included'],
        'password_manager': ['Keeper', 'Not Included'],
        'sat': ['BSN', 'Not Included'],
        'soc': ['RocketCyber', 'Not Included'],
        'support_level': ['Unlimited', 'Hourly']
    }

    created_count = 0
    existing_count = 0

    # Fetch all existing features first to avoid autoflush issues
    existing_features = {}
    for feature in FeatureOption.query.all():
        key = (feature.feature_type, feature.display_name)
        existing_features[key] = feature

    for feature_type, options in features.items():
        for option in options:
            key = (feature_type, option)

            if key not in existing_features:
                feature = FeatureOption(
                    feature_type=feature_type,
                    display_name=option,
                    description=f"{option} option for {feature_type.replace('_', ' ').title()}"
                )
                db.session.add(feature)
                created_count += 1
            else:
                existing_count += 1

    db.session.commit()
    print(f"  ✓ Created {created_count} feature options, {existing_count} already existed")
    print("✓ Feature options setup complete!")


def create_sample_scheduler_jobs():
    """Creates sample scheduler jobs for initial setup."""
    print("\n--- Creating Scheduler Jobs ---")

    sample_jobs = [
        {
            'job_name': 'Sync Companies/Assets/Users from Codex',
            'script_path': 'sync_from_codex.py',
            'schedule_cron': '0 */4 * * *',
            'description': 'Syncs company, asset, and user data from Codex service (primary data source)',
            'enabled': True
        },
        {
            'job_name': 'Sync Ticket Details from Freshservice',
            'script_path': 'sync_tickets_from_freshservice.py',
            'schedule_cron': '0 */6 * * *',
            'description': 'Pulls ticket data and hours from Freshservice API for billing calculations',
            'enabled': False
        },
        {
            'job_name': 'Sync Backup Data from Datto RMM',
            'script_path': 'sync_backup_data_from_datto.py',
            'schedule_cron': '0 2 * * *',
            'description': 'Pulls backup storage data from Datto RMM UDF fields for backup billing',
            'enabled': False
        }
    ]

    created_count = 0
    existing_count = 0

    for job_data in sample_jobs:
        existing = SchedulerJob.query.filter_by(job_name=job_data['job_name']).first()

        if not existing:
            job = SchedulerJob(**job_data)
            db.session.add(job)
            created_count += 1
        else:
            existing_count += 1

    db.session.commit()
    print(f"  ✓ Created {created_count} scheduler jobs, {existing_count} already existed")
    print("✓ Scheduler jobs setup complete!")


def configure_freshservice(config):
    """Configure Freshservice API credentials."""
    print("\n" + "="*70)
    print("Freshservice Configuration (Optional - for ticket sync)")
    print("="*70)

    # Check for existing config
    existing_key = config.get('freshservice', 'api_key', fallback='')
    existing_domain = config.get('freshservice', 'domain', fallback='integotecllc.freshservice.com')

    if existing_key:
        reconfigure = input(f"\nFreshservice already configured (domain: {existing_domain}). Reconfigure? (y/n): ").lower() == 'y'
        if not reconfigure:
            print("Keeping existing Freshservice configuration.")
            return
    else:
        configure = input("\nConfigure Freshservice? (y/n): ").lower() == 'y'
        if not configure:
            print("Skipping Freshservice configuration.")
            return

    api_key = input(f"Freshservice API Key [{existing_key[:10] + '...' if existing_key else ''}]: ").strip() or existing_key
    domain = input(f"Freshservice Domain [{existing_domain}]: ").strip() or existing_domain

    if api_key:
        if not config.has_section('freshservice'):
            config.add_section('freshservice')
        config.set('freshservice', 'api_key', api_key)
        config.set('freshservice', 'domain', domain)
        print("✓ Freshservice credentials saved")
    else:
        print("⚠ No API key provided, skipping Freshservice configuration")


def configure_datto(config):
    """Configure Datto RMM API credentials."""
    print("\n" + "="*70)
    print("Datto RMM Configuration (Optional - for backup data sync)")
    print("="*70)

    # Check for existing config
    existing_endpoint = config.get('datto', 'api_endpoint', fallback='https://pinotage-api.centrastage.net')
    existing_key = config.get('datto', 'api_key', fallback='')
    existing_secret = config.get('datto', 'api_secret', fallback='')
    existing_udf = config.get('datto', 'backup_udf_id', fallback='6')

    if existing_key:
        reconfigure = input(f"\nDatto RMM already configured (endpoint: {existing_endpoint}). Reconfigure? (y/n): ").lower() == 'y'
        if not reconfigure:
            print("Keeping existing Datto RMM configuration.")
            return
    else:
        configure = input("\nConfigure Datto RMM? (y/n): ").lower() == 'y'
        if not configure:
            print("Skipping Datto RMM configuration.")
            return

    api_endpoint = input(f"Datto API Endpoint [{existing_endpoint}]: ").strip() or existing_endpoint
    api_key = input(f"Datto API Key [{existing_key[:10] + '...' if existing_key else ''}]: ").strip() or existing_key
    api_secret = input(f"Datto API Secret [{existing_secret[:10] + '...' if existing_secret else ''}]: ").strip() or existing_secret
    backup_udf_id = input(f"Backup UDF ID [{existing_udf}]: ").strip() or existing_udf

    if api_key and api_secret:
        if not config.has_section('datto'):
            config.add_section('datto')
        config.set('datto', 'api_endpoint', api_endpoint)
        config.set('datto', 'api_key', api_key)
        config.set('datto', 'api_secret', api_secret)
        config.set('datto', 'backup_udf_id', backup_udf_id)
        print("✓ Datto RMM credentials saved")
    else:
        print("⚠ API key or secret missing, skipping Datto RMM configuration")


def init_db():
    """Interactively configures and initializes the database."""
    instance_path = app.instance_path
    config_path = os.path.join(instance_path, 'ledger.conf')

    config = configparser.RawConfigParser()

    if os.path.exists(config_path):
        config.read(config_path)
        print(f"\n✓ Existing configuration found: {config_path}")
    else:
        print(f"\n→ Creating new config: {config_path}")
        os.makedirs(instance_path, exist_ok=True)

    # Database configuration
    while True:
        creds = get_db_credentials(config)
        conn_string, success = test_db_connection(creds)
        if success:
            if not config.has_section('database'):
                config.add_section('database')
            config.set('database', 'connection_string', conn_string)

            if not config.has_section('database_credentials'):
                config.add_section('database_credentials')
            for key, val in creds.items():
                if key != 'password':
                    config.set('database_credentials', f'db_{key}', val)
            break
        else:
            if input("\nRetry? (y/n): ").lower() != 'y':
                sys.exit("Database configuration aborted.")

    # Configure external systems
    configure_freshservice(config)
    configure_datto(config)

    # Save configuration
    with open(config_path, 'w') as configfile:
        config.write(configfile)
    print(f"\n✓ Configuration saved to: {config_path}")

    # Initialize database schema
    with app.app_context():
        print("\nInitializing database schema...")
        db.create_all()
        print("✓ Database schema initialized successfully!")

        # Create sample data
        create_sample = input("\nCreate billing plans and features? (y/n): ").lower() == 'y'
        if create_sample:
            create_sample_billing_plans()
            create_feature_options()

        create_jobs = input("\nCreate scheduler jobs? (y/n): ").lower() == 'y'
        if create_jobs:
            create_sample_scheduler_jobs()

    print("\n" + "="*50)
    print("✓ HiveMatrix Ledger Database Initialization Complete!")
    print("="*50)
    print("\nYou can now start the service with: flask run --port=5030")


if __name__ == '__main__':
    init_db()
