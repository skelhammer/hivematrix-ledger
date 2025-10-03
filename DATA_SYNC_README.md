# HiveMatrix Ledger - Data Sync Architecture

## Overview

**Ledger is a billing service that pulls all data from Codex via API.**

Ledger does NOT sync directly from external services (Freshservice, Datto RMM). All data syncing is centralized in the Codex service.

## Architecture

```
External Services (Freshservice, Datto)
    ↓
Codex (Central Data Hub)
    - Syncs from Freshservice (companies, contacts, tickets)
    - Syncs from Datto RMM (assets, backup data)
    - Provides API endpoints for other services
    ↓
Ledger (Billing Service)
    - Fetches data from Codex API
    - Calculates billing
    - Stores billing-specific data (plans, overrides, custom line items)
```

## Data Flow

1. **Codex Admin** triggers syncs from Codex dashboard:
   - Sync Freshservice → Companies, Contacts
   - Sync Datto RMM → Assets, Backup Data
   - Sync Tickets → Billing Hours

2. **Ledger** fetches data from Codex:
   - `/api/companies` - All companies
   - `/api/companies/{account}/assets` - Assets with backup data
   - `/api/companies/{account}/contacts` - Users/contacts
   - `/api/companies/{account}/tickets` - Tickets for billing hours

3. **Ledger** performs billing calculations using:
   - Data from Codex (companies, assets, users, tickets)
   - Billing-specific data from Ledger DB (plans, overrides, custom items)

## Deprecated Scripts

The following scripts are DEPRECATED and should NOT be used:

- ❌ `sync_tickets_from_freshservice.py.deprecated` - Use Codex ticket sync instead
- ❌ `sync_backup_data_from_datto.py.deprecated` - Use Codex Datto sync instead

## Active Sync Script

- ✅ `sync_from_codex.py` - Diagnostic tool to test Codex connectivity (optional)

## How to Sync Data

### Via Codex Dashboard (Recommended)

1. Log into Codex as admin: `http://localhost:5001`
2. Navigate to "Data Sync Center" section
3. Click sync buttons in order:
   - **Sync Freshservice** (companies & contacts)
   - **Sync Datto RMM** (assets & backup)
   - **Sync Tickets** (billing hours - may take hours)

### Via Command Line

```bash
cd /path/to/hivematrix-codex

# Sync companies and contacts from Freshservice
python pull_freshservice.py

# Sync assets and backup data from Datto RMM
python pull_datto.py

# Sync tickets for billing hours
python sync_tickets_from_freshservice.py
```

## Troubleshooting

### Ledger shows no billing data

1. Verify Codex service is running
2. Check Codex has data (log into Codex dashboard)
3. Verify `services.json` has correct Codex URL
4. Check Ledger logs for API errors

### Backup data is zero

1. Verify Datto sync ran successfully in Codex
2. Check Codex assets have `backup_usage_tb` values
3. Ledger converts TB to bytes automatically

### Hours data is missing

1. Verify ticket sync completed in Codex (may take hours)
2. Check Codex `/api/companies/{account}/tickets` endpoint
3. Ensure tickets are for the current year

## Configuration

Ledger only needs to know where Codex is:

```json
// services.json
{
  "codex": {
    "url": "http://localhost:5001",
    "api_key": "your_api_key_here"
  }
}
```

All external service credentials (Freshservice, Datto) are configured in **Codex**, not Ledger.
