# HiveMatrix Ledger

**Billing and Financial Management Service for HiveMatrix**

## Overview

HiveMatrix Ledger is a dedicated billing service that manages all financial calculations, billing plans, rate overrides, and custom line items for the HiveMatrix platform. It integrates with Codex to fetch company, asset, and user data for billing calculations.

## Architecture

Ledger follows the HiveMatrix monolithic service pattern:
- **Service Name**: `ledger`
- **Port**: 5030
- **Authentication**: JWT-based via Core service
- **Database**: PostgreSQL (ledger_db)
- **Data Sources**:
  - Codex (company/asset/user data via service-to-service calls)
  - Local database (billing plans, overrides, custom items)
  - Optional: Freshservice (ticket hours for billing)

## Key Features

- **Billing Plans Management**: Define base pricing structures with term lengths
- **Client-Specific Overrides**: Customize rates per client
- **Asset/User Overrides**: Override billing types for specific assets/users
- **Manual Assets/Users**: Add billable items not in Codex
- **Custom Line Items**: One-off, recurring, or yearly charges
- **Ticket Hour Tracking**: Integrate ticket hours for hourly billing
- **Backup Billing**: Automated backup storage calculations
- **Contract Management**: Track contract terms and expiration

## Installation

### 1. Install PostgreSQL (Ubuntu)

**Skip this section if PostgreSQL is already installed.**

```bash
# Update package list
sudo apt update

# Install PostgreSQL
sudo apt install postgresql postgresql-contrib -y

# Start PostgreSQL service
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Verify installation
sudo systemctl status postgresql
```

### 2. Create Database and User

```bash
# Switch to postgres user
sudo -u postgres psql

# In PostgreSQL prompt, run:
CREATE DATABASE ledger_db;
CREATE USER ledger_user WITH PASSWORD 'your_secure_password_here';
GRANT ALL PRIVILEGES ON DATABASE ledger_db TO ledger_user;

# Grant schema permissions (PostgreSQL 15+)
\c ledger_db
GRANT ALL ON SCHEMA public TO ledger_user;

# Exit PostgreSQL
\q
```

### 3. Install Python Dependencies

```bash
cd hivematrix-ledger
python -m venv pyenv
source pyenv/bin/activate
pip install -r requirements.txt
```

### 4. Configure Environment

The `.flaskenv` file is already configured:
```
FLASK_APP=run.py
FLASK_ENV=development
CORE_SERVICE_URL='http://localhost:5000'
SERVICE_NAME='ledger'
```

### 5. Initialize Database Schema and Configure External Systems

```bash
python init_db.py
```

This interactive script will walk you through:

1. **PostgreSQL Connection**
   - Host (default: localhost)
   - Port (default: 5432)
   - Database (default: ledger_db)
   - User (default: ledger_user)
   - Password

2. **Freshservice Configuration** (Optional)
   - API Key
   - Domain (default: integotecllc.freshservice.com)
   - Used for syncing ticket hours for billing

3. **Datto RMM Configuration** (Optional)
   - API Endpoint (default: https://pinotage-api.centrastage.net)
   - API Key
   - API Secret
   - Backup UDF ID (default: 6)
   - Used for syncing backup storage data for billing

4. **Sample Data Creation**
   - Sample billing plans (recommended for testing)
   - Sample scheduler jobs (Freshservice & Datto pullers)

**Example session:**
```
--- PostgreSQL Database Configuration ---
Host [localhost]:
Port [5432]:
Database Name [ledger_db]:
User [ledger_user]:
Password: ********

✓ Database connection successful!

======================================================================
Freshservice Configuration (Optional - for ticket sync)
======================================================================

Configure Freshservice? (y/n): y
Freshservice API Key: your_api_key_here
Freshservice Domain [integotecllc.freshservice.com]:
✓ Freshservice credentials saved

======================================================================
Datto RMM Configuration (Optional - for backup data sync)
======================================================================

Configure Datto RMM? (y/n): y
Datto API Endpoint [https://pinotage-api.centrastage.net]:
Datto API Key: your_api_key_here
Datto API Secret: your_api_secret_here
Backup UDF ID [6]:
✓ Datto RMM credentials saved

✓ Configuration saved to: instance/ledger.conf
✓ Database schema initialized successfully!

Create sample billing plans? (y/n): y
✓ Sample billing plans created successfully!

Create sample scheduler jobs? (y/n): y
✓ Sample scheduler jobs created successfully!
```

**Note:** You can skip the external system configuration during setup and add credentials later by editing `instance/ledger.conf` manually or re-running `init_db.py`.

### 6. Start the Service

```bash
# Make sure virtual environment is activated
source pyenv/bin/activate

# Start the service
# flask run --port=5030
```

The service will be available at:
- Direct: `http://localhost:5030`
- Via Nexus: `http://localhost:8000/ledger/`

## Database Models

### Core Tables
- **billing_plans**: Base pricing plans with term lengths
- **client_billing_overrides**: Per-client rate customizations
- **asset_billing_overrides**: Override billing types for assets
- **user_billing_overrides**: Override billing types for users
- **manual_assets**: Manually added billable assets
- **manual_users**: Manually added billable users
- **custom_line_items**: Custom charges (recurring/one-off/yearly)
- **ticket_details**: Ticket hours for billing calculations

## API Endpoints

### User Interfaces (require billing/admin permissions)
- `GET /` - Billing dashboard
- `GET /client/{account}` - Client billing details
- `GET /client/{account}/settings` - Billing configuration
- `GET /admin/plans` - Manage billing plans (admin only)

### API Endpoints (work for services too)
- `GET /api/billing/{account}` - Get billing data for account
- `GET /api/billing/dashboard` - Get dashboard data for all clients
- `GET /api/plans` - List all billing plans

## Service Integration

### Calling from Other Services

```python
from app.service_client import call_service

# Get billing data
response = call_service('ledger', '/api/billing/ACCT001')
billing_data = response.json()

# Get dashboard data
response = call_service('ledger', '/api/billing/dashboard?year=2025&month=3')
dashboard = response.json()
```

### Data Flow

1. User requests billing data via Nexus
2. Ledger fetches company/asset/user data from Codex
3. Ledger retrieves local billing configuration (plans, overrides)
4. Billing engine calculates charges
5. Results returned to user or calling service

## Sync Scripts

### Running Pullers Manually

You can run any puller script directly:

```bash
# Sync ticket hours from Freshservice
python sync_tickets_from_freshservice.py

# Sync backup data from Datto RMM
python sync_backup_data_from_datto.py
```

### Running Pullers via Admin UI

1. Navigate to **Admin → Data Pullers**
2. Find the puller you want to run
3. Click **▶ Run Now**
4. Monitor progress in real-time
5. View detailed logs after completion

### Automated Scheduling (Cron)

For automated syncing outside the admin UI, set up cron jobs:

```bash
# Every 6 hours - Sync ticket data
0 */6 * * * cd /path/to/hivematrix-ledger && ./pyenv/bin/python sync_tickets_from_freshservice.py

# Daily at 2 AM - Sync backup data
0 2 * * * cd /path/to/hivematrix-ledger && ./pyenv/bin/python sync_backup_data_from_datto.py
```

**Note:** Cron schedules configured in the admin UI are for reference only. You must set up actual cron jobs separately if you want automated execution outside the admin panel's manual "Run Now" feature.

## Billing Calculation Logic

The billing engine (`app/billing_engine.py`) calculates:

1. **Asset Charges**: Per-asset costs based on type (workstation, server, VM, etc.)
2. **User Charges**: Per-user costs (paid vs free users)
3. **Ticket Charges**: Hourly billing with prepaid hour deduction
4. **Backup Charges**: Base fees + overage charges for backup storage
5. **Custom Line Items**: Recurring, one-off, or yearly charges

All calculations respect:
- Client-specific rate overrides
- Asset/user billing type overrides
- Prepaid hours (monthly and yearly)
- Contract terms and pricing

## Admin Features

The ledger service includes comprehensive admin functionality accessible to users with **admin** permission level:

### Admin Dashboard (`/admin/settings`)
Central hub showing:
- Summary statistics (plans, features, pullers)
- Quick links to all admin sections
- Recent puller run status

### Billing Plans Management (`/admin/plans`)
- Create/edit/delete billing plans
- Configure rates for different term lengths (Month to Month, 1-Year, 2-Year, 3-Year)
- Set per-item costs (users, workstations, servers, VMs, etc.)
- Configure backup pricing
- Set hourly ticket rates

### Feature Options Management (`/admin/features`)
- Create custom feature types for billing
- Configure feature options available to clients
- Manage feature descriptions

### Data Pullers & Sync Jobs (`/admin/pullers`)
- **Configure automated sync jobs** (replicates integodash scheduler functionality)
- **Run pullers manually** with real-time status
- **View detailed logs** from each puller run
- Configure cron schedules for automated execution
- Enable/disable individual pullers
- Track last run time and status (Success/Failure/Running)

Example pullers you can configure:
- `sync_tickets_from_freshservice.py` - Pull ticket hours for billing
- Custom sync scripts for other data sources
- Any Python script in the project directory

### Puller Status Tracking
Each puller job tracks:
- **Job Name** and description
- **Script Path** to execute
- **Schedule** (cron expression)
- **Last Run** timestamp
- **Status** (Success ✓, Failure ✗, Running ⏳, Timeout ⚠)
- **Full Output Log** (stdout/stderr)
- **Enabled/Disabled** state

## Permissions

- **billing**: Can view and manage billing data, client settings
- **admin**: Can access all admin features, manage plans, run pullers, configure system
- **Services**: Full API access for integration

## Development

### Adding New Features

1. Add database models to `models.py`
2. Create migration or update `init_db.py`
3. Add business logic to `app/billing_engine.py`
4. Create routes in `app/routes.py`
5. Add templates in `app/templates/`

### Testing

```bash
# Test service connectivity
curl http://localhost:5030/api/plans -H "Authorization: Bearer <token>"

# Test billing calculation
curl http://localhost:5030/api/billing/ACCT001?year=2025&month=3 -H "Authorization: Bearer <token>"
```

## Migration from Integodash

This service replaces the billing functionality from the legacy `integodash` application:

**Removed**:
- Standalone authentication (now uses Core JWT)
- Encrypted SQLite (now uses PostgreSQL)
- Direct Datto/Freshservice pulls for companies/assets (now via Codex)
- All CSS/styling (handled by Nexus)
- Knowledge base, contacts, assets management (moved to other services)

**Preserved**:
- Core billing calculation engine
- Billing plans and overrides
- Custom line items
- Ticket hour tracking
- Backup billing logic

## Support

For issues or questions, refer to the main HiveMatrix documentation or the `ARCHITECTURE.md` in hivematrix-core.
