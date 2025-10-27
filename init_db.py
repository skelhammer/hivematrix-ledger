import argparse
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
            'job_name': 'Diagnostic: Test Codex Connectivity',
            'script_path': 'sync_from_codex.py',
            'schedule_cron': '0 */12 * * *',
            'description': 'Diagnostic tool to verify Codex API connectivity and data availability',
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




def init_db_headless(db_host, db_port, db_name, db_user, db_password, migrate_only=False, create_sample_data=False):
    """Non-interactive database initialization for automated installation."""
    from urllib.parse import quote_plus

    print("\n" + "="*80)
    print("LEDGER DATABASE INITIALIZATION (HEADLESS MODE)")
    print("="*80)

    instance_path = app.instance_path
    os.makedirs(instance_path, exist_ok=True)
    config_path = os.path.join(instance_path, 'ledger.conf')

    config = configparser.RawConfigParser()

    # Build connection string
    escaped_password = quote_plus(db_password)
    conn_string = f"postgresql://{db_user}:{escaped_password}@{db_host}:{db_port}/{db_name}"

    # Test connection
    print(f"\n→ Testing database connection to {db_host}:{db_port}/{db_name}...")
    try:
        engine = create_engine(conn_string)
        with engine.connect() as connection:
            print("✓ Database connection successful")
    except Exception as e:
        print(f"✗ Connection failed: {e}", file=sys.stderr)
        sys.exit(1)

    # Save configuration
    if not config.has_section('database'):
        config.add_section('database')
    config.set('database', 'connection_string', conn_string)

    if not config.has_section('database_credentials'):
        config.add_section('database_credentials')
    config.set('database_credentials', 'db_host', db_host)
    config.set('database_credentials', 'db_port', db_port)
    config.set('database_credentials', 'db_name', db_name)
    config.set('database_credentials', 'db_user', db_user)

    with open(config_path, 'w') as configfile:
        config.write(configfile)
    print(f"✓ Configuration saved to: {config_path}")

    # Initialize database schema
    print("\n→ Initializing database schema...")
    with app.app_context():
        db.create_all()
        print("✓ Database schema initialized successfully!")

        if create_sample_data:
            print("\n→ Creating sample billing plans and features...")
            create_sample_billing_plans()
            create_feature_options()
            create_sample_scheduler_jobs()
            print("✓ Sample data created")

    print("\n" + "="*80)
    print(" ✓ Ledger Initialization Complete!")
    print("="*80)



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

    # Note: Ledger pulls all operational data from Codex via API
    # Configure Codex connection in services.json, not here
    print("\n" + "="*70)
    print("IMPORTANT: Ledger pulls data from Codex, not external services")
    print("="*70)
    print("Configure Codex connection in services.json:")
    print('  {"codex": {"url": "http://localhost:5001", "api_key": "..."}}')
    print("="*70)

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
    parser = argparse.ArgumentParser(
        description='Initialize Ledger database schema',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        '--headless',
        action='store_true',
        help='Non-interactive mode for automated installation'
    )
    parser.add_argument(
        '--db-host',
        type=str,
        default='localhost',
        help='Database host (default: localhost)'
    )
    parser.add_argument(
        '--db-port',
        type=str,
        default='5432',
        help='Database port (default: 5432)'
    )
    parser.add_argument(
        '--db-name',
        type=str,
        default='ledger_db',
        help='Database name (default: ledger_db)'
    )
    parser.add_argument(
        '--db-user',
        type=str,
        default='ledger_user',
        help='Database user (default: ledger_user)'
    )
    parser.add_argument(
        '--db-password',
        type=str,
        help='Database password (required for headless mode)'
    )
    parser.add_argument(
        '--migrate-only',
        action='store_true',
        help='Only run migrations on existing database'
    )
    parser.add_argument(
        '--create-sample-data',
        action='store_true',
        help='Create sample billing plans and features (headless mode only)'
    )

    args = parser.parse_args()

    if args.headless:
        if not args.db_password:
            print("ERROR: --db-password is required for headless mode", file=sys.stderr)
            sys.exit(1)

        init_db_headless(
            db_host=args.db_host,
            db_port=args.db_port,
            db_name=args.db_name,
            db_user=args.db_user,
            db_password=args.db_password,
            migrate_only=args.migrate_only,
            create_sample_data=args.create_sample_data
        )
    else:
        init_db()
