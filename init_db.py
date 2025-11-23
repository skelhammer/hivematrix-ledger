import argparse
import os
import sys
import configparser
import json
import subprocess
from getpass import getpass
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import OperationalError
from dotenv import load_dotenv

load_dotenv('.flaskenv')
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# NOTE: We import app later in functions to allow config file to be created first
# For headless mode, app is imported AFTER config file is written
app = None
db = None

def _import_app():
    """Import app and db after config file exists."""
    global app, db
    if app is None:
        from app import app as flask_app
        from extensions import db as database
        # Import ALL models so SQLAlchemy knows about them
        # NOTE: BillingPlan and FeatureOption removed - now fetched from Codex via API
        from models import (
            ClientBillingOverride, AssetBillingOverride, UserBillingOverride,
            ManualAsset, ManualUser, CustomLineItem, TicketDetail, ClientFeatureOverride,
            SchedulerJob,
            # Archive models (merged from hivematrix-archive)
            BillingSnapshot, SnapshotLineItem, ScheduledSnapshot, SnapshotJob
        )
        app = flask_app
        db = database
    return app, db


def get_db_credentials(config):
    """Prompts the user for PostgreSQL connection details."""
    print("\n--- PostgreSQL Database Configuration ---")

    # Load existing or use defaults
    db_details = {
        'host': config.get('database_credentials', 'db_host', fallback='localhost'),
        'port': config.get('database_credentials', 'db_port', fallback='5432'),
        'user': config.get('database_credentials', 'db_user', fallback='ledger_user'),
        'dbname': config.get('database_credentials', 'db_name', fallback='ledger_db')
    }

    host = input(f"Host [{db_details['host']}]: ") or db_details['host']
    port = input(f"Port [{db_details['port']}]: ") or db_details['port']
    dbname = input(f"Database Name [{db_details['dbname']}]: ") or db_details['dbname']
    user = input(f"User [{db_details['user']}]: ") or db_details['user']

    # Try to get password from config first (won't be stored, but helpful for re-runs in same session)
    password = getpass("Password: ")

    return {'host': host, 'port': port, 'dbname': dbname, 'user': user, 'password': password}


def test_db_connection(creds):
    """Tests the database connection, automatically creating database if needed."""
    from urllib.parse import quote_plus

    # First check if database exists using psql
    check_cmd = f"sudo -u postgres psql -tAc \"SELECT 1 FROM pg_database WHERE datname='{creds['dbname']}'\""
    try:
        result = subprocess.run(check_cmd, shell=True, capture_output=True, text=True, timeout=5)
        db_exists = "1" in result.stdout
    except Exception:
        db_exists = False

    # Create database if it doesn't exist
    if not db_exists:
        print(f"\n→ Database '{creds['dbname']}' does not exist. Creating it...")
        create_cmd = f"sudo -u postgres psql -c \"CREATE DATABASE {creds['dbname']} OWNER {creds['user']};\""
        try:
            result = subprocess.run(create_cmd, shell=True, capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                print(f"✓ Database '{creds['dbname']}' created successfully!")
            else:
                print(f"\n✗ Failed to create database: {result.stderr}", file=sys.stderr)
                print(f"  You may need to create it manually:")
                print(f"  sudo -u postgres psql -c \"CREATE DATABASE {creds['dbname']} OWNER {creds['user']};\"")
                return None, False
        except Exception as e:
            print(f"\n✗ Failed to create database: {e}", file=sys.stderr)
            return None, False

    escaped_password = quote_plus(creds['password'])
    conn_string = f"postgresql+psycopg2://{creds['user']}:{escaped_password}@{creds['host']}:{creds['port']}/{creds['dbname']}"

    try:
        engine = create_engine(conn_string)
        with engine.connect() as connection:
            print("\n✓ Database connection successful!")
            return conn_string, True
    except OperationalError as e:
        print(f"\n✗ Connection failed: {e}", file=sys.stderr)
        return None, False


def migrate_schema():
    """
    Intelligently migrates database schema without losing data.

    This function:
    1. Inspects existing tables and columns
    2. Compares with models defined in models.py
    3. Adds missing columns (with defaults)
    4. Creates missing tables
    5. Does NOT drop columns or tables (safe for production)
    """
    print("\n" + "="*80)
    print("DATABASE SCHEMA MIGRATION")
    print("="*80)

    app, db = _import_app()
    with app.app_context():
        inspector = inspect(db.engine)
        existing_tables = inspector.get_table_names()

        print(f"\nFound {len(existing_tables)} existing tables in database")

        # Get all tables defined in models
        model_tables = db.metadata.tables

        # Track changes
        tables_created = []
        columns_added = []

        # Create tables in dependency order (association tables last)
        base_tables = []
        association_tables = []

        for table_name, table in model_tables.items():
            if 'link' in table_name.lower() or len([c for c in table.columns if c.foreign_keys]) >= 2:
                association_tables.append((table_name, table))
            else:
                base_tables.append((table_name, table))

        # Create base tables first
        for table_name, table in base_tables:
            if table_name not in existing_tables:
                print(f"\n→ Creating new table: {table_name}")
                table.create(db.engine)
                tables_created.append(table_name)

        # Then create association tables
        for table_name, table in association_tables:
            if table_name not in existing_tables:
                print(f"\n→ Creating new association table: {table_name}")
                table.create(db.engine)
                tables_created.append(table_name)

        # Check all tables for missing columns
        for table_name, table in base_tables + association_tables:
            if table_name in existing_tables:
                existing_columns = {col['name'] for col in inspector.get_columns(table_name)}
                model_columns = {col.name for col in table.columns}
                missing_columns = model_columns - existing_columns

                if missing_columns:
                    print(f"\n→ Updating table '{table_name}' - adding {len(missing_columns)} columns:")

                    import re
                    if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', table_name):
                        print(f"   ✗ Invalid table name format: {table_name}")
                        continue

                    for col_name in missing_columns:
                        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', col_name):
                            print(f"   ✗ Invalid column name format: {col_name}")
                            continue

                        col = table.columns[col_name]
                        col_type = col.type.compile(db.engine.dialect)

                        nullable = "NULL" if col.nullable else "NOT NULL"
                        default = ""

                        if col.default is not None:
                            if hasattr(col.default, 'arg'):
                                default_val = col.default.arg
                                if isinstance(default_val, str):
                                    default = f"DEFAULT '{default_val}'"
                                elif isinstance(default_val, bool):
                                    default = f"DEFAULT {str(default_val).upper()}"
                                else:
                                    default = f"DEFAULT {default_val}"

                        if not col.nullable and not default:
                            nullable = "NULL"
                            print(f"   ⚠ Column '{col_name}' is NOT NULL but has no default - making nullable for safety")

                        sql = f'ALTER TABLE "{table_name}" ADD COLUMN "{col_name}" {col_type} {default} {nullable}'

                        try:
                            with db.engine.connect() as conn:
                                conn.execute(text(sql))
                                conn.commit()
                            print(f"   ✓ Added column: {col_name} ({col_type})")
                            columns_added.append(f"{table_name}.{col_name}")
                        except Exception as e:
                            print(f"   ✗ Failed to add column {col_name}: {e}")

        # Summary
        print("\n" + "="*80)
        print("MIGRATION SUMMARY")
        print("="*80)

        if tables_created:
            print(f"\n✓ Created {len(tables_created)} new table(s):")
            for t in tables_created:
                print(f"  - {t}")
        else:
            print("\n• No new tables created")

        if columns_added:
            print(f"\n✓ Added {len(columns_added)} new column(s):")
            for c in columns_added:
                print(f"  - {c}")
        else:
            print("\n• No new columns added")

        if not tables_created and not columns_added:
            print("\n✓ Schema is up to date - no changes needed")

        print("\n" + "="*80)


# NOTE: Billing plan and feature creation functions REMOVED
# These are now managed in Codex only. Ledger fetches them via API.
# See app/codex_client.py for billing plan API integration


def create_sample_scheduler_jobs():
    """Creates sample scheduler jobs for initial setup."""
    app, db = _import_app()
    from models import SchedulerJob
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

    # Determine instance path without importing app yet
    script_dir = os.path.dirname(os.path.abspath(__file__))
    instance_path = os.path.join(script_dir, 'instance')
    os.makedirs(instance_path, exist_ok=True)
    config_path = os.path.join(instance_path, 'ledger.conf')

    config = configparser.RawConfigParser()

    # Build connection string
    escaped_password = quote_plus(db_password)
    conn_string = f"postgresql+psycopg2://{db_user}:{escaped_password}@{db_host}:{db_port}/{db_name}"

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

    # Run schema migration
    migrate_schema()

    # Import app for sample data creation if needed
    if create_sample_data:
        app, db = _import_app()
        with app.app_context():
            print("\n→ Creating sample scheduler jobs...")
            create_sample_scheduler_jobs()
            print("✓ Sample data created")
            print("\nℹ Billing plans are managed in Codex - import them there if needed")

    print("\n" + "="*80)
    print(" ✓ Ledger Initialization Complete!")
    print("="*80)



def init_db():
    """Interactively configures and initializes the database."""
    app, db = _import_app()
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

    # Run schema migration
    print("\nInitializing database schema...")
    migrate_schema()

    # Create sample scheduler jobs
    with app.app_context():
        create_jobs = input("\nCreate scheduler jobs? (y/n): ").lower() == 'y'
        if create_jobs:
            create_sample_scheduler_jobs()

        print("\nℹ Billing plans are managed in Codex - import them there if needed")

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
