# HiveMatrix Ledger

Billing calculation and invoicing engine for MSP customer billing.

## Overview

Ledger calculates customer bills based on per-unit pricing, billing plans, and asset counts from Codex. It supports custom rate overrides and recurring line items for flexible billing.

**Port:** 5030

## Features

- **Per-Unit Pricing** - Rates for users, servers, workstations, VMs
- **Billing Plans** - Tiered service plans with default rates
- **Rate Overrides** - Custom pricing per customer
- **Line Items** - Additional monthly charges
- **Contract Terms** - Month-to-month, 1/2/3 year terms
- **Invoice Generation** - Detailed billing breakdowns

## Tech Stack

- Flask + Gunicorn
- PostgreSQL
- SQLAlchemy ORM

## Key Endpoints

- `GET /api/billing/<account>` - Get billing for account
- `GET /api/plans` - List available billing plans
- `GET /api/overrides/client/<account>` - Get rate overrides
- `PUT /api/overrides/client/<account>` - Set rate overrides
- `POST /api/overrides/line-items/<account>` - Add line item

## Billing Calculation

```
Total = User Charges + Asset Charges + Line Items - Prepaid Credits
```

Asset charges include:
- Workstations, Servers, VMs
- Switches, Firewalls
- Backup storage

## Environment Variables

- `CORE_SERVICE_URL` - Core service URL
- `CODEX_SERVICE_URL` - Codex service URL

## Dependencies

Ledger requires:
- **Codex** - For company and asset counts

## Documentation

For complete installation, configuration, and architecture documentation:

**[HiveMatrix Documentation](https://skelhammer.github.io/hivematrix-docs/)**

## License

MIT License - See LICENSE file
