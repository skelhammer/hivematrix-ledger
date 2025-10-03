#!/usr/bin/env python3
"""
Sync Data from Codex Service

This script fetches company, asset, and user data from the Codex service.
This is the primary data source for billing calculations.

Note: Currently, this script logs what it would sync. In a full implementation,
you might cache this data locally or use it to validate/supplement billing data.
"""

import sys
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv('.flaskenv')
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app
from app.codex_client import get_all_companies, get_company_assets, get_company_contacts


def sync_companies():
    """Fetch and log all companies from Codex."""
    print("\n--- Syncing Companies from Codex ---")

    companies = get_all_companies()

    if not companies:
        print("⚠ No companies found or error fetching from Codex")
        return 0

    print(f"✓ Found {len(companies)} companies in Codex")

    # Log summary
    for company in companies:
        account_number = company.get('account_number')
        name = company.get('name')
        billing_plan = company.get('billing_plan', 'Not Set')
        print(f"  - {account_number}: {name} (Plan: {billing_plan})")

    return len(companies)


def sync_assets_and_users():
    """Fetch assets and users for all companies."""
    print("\n--- Syncing Assets and Users from Codex ---")

    companies = get_all_companies()
    if not companies:
        print("⚠ No companies to sync assets/users for")
        return 0, 0

    total_assets = 0
    total_users = 0

    for company in companies:
        account_number = company.get('account_number')
        if not account_number:
            continue

        name = company.get('name', 'Unknown')

        # Fetch assets
        assets = get_company_assets(account_number)
        asset_count = len(assets) if assets else 0
        total_assets += asset_count

        # Fetch users/contacts
        users = get_company_contacts(account_number)
        user_count = len(users) if users else 0
        total_users += user_count

        print(f"  {account_number}: {name}")
        print(f"    → Assets: {asset_count}, Users: {user_count}")

    return total_assets, total_users


def main():
    """Main execution."""
    print("="*70)
    print("HiveMatrix Ledger - Codex Data Sync")
    print("="*70)
    print(f"Sync started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    with app.app_context():
        # Sync companies
        company_count = sync_companies()

        # Sync assets and users
        asset_count, user_count = sync_assets_and_users()

    # Summary
    print("\n" + "="*70)
    print("Sync Summary:")
    print(f"  Companies: {company_count}")
    print(f"  Total Assets: {asset_count}")
    print(f"  Total Users: {user_count}")
    print("="*70)

    if company_count > 0:
        print("\n✓ Codex sync complete!")
        print("\nNote: This data is fetched from Codex on-demand for billing.")
        print("No local caching is performed - all billing calculations")
        print("use real-time data from Codex service.")
    else:
        print("\n⚠ Codex sync completed with warnings")
        print("Check that Codex service is running and accessible.")
        sys.exit(1)


if __name__ == '__main__':
    main()
