#!/usr/bin/env python3
"""
Sync Ticket Details from Freshservice for Billing

This script pulls ticket data from Freshservice and stores it in the ledger database
for billing calculations. It can be run manually or via cron.
"""

import os
import sys
import configparser
import requests
import base64
from datetime import datetime
from dotenv import load_dotenv

load_dotenv('.flaskenv')
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app
from extensions import db
from models import TicketDetail


def get_freshservice_credentials():
    """Get Freshservice API credentials from config."""
    config_path = os.path.join(app.instance_path, 'ledger.conf')
    config = configparser.RawConfigParser()
    config.read(config_path)

    if not config.has_section('freshservice'):
        print("ERROR: Freshservice credentials not found in config.")
        print("Please add [freshservice] section with api_key and domain.")
        sys.exit(1)

    return {
        'api_key': config.get('freshservice', 'api_key'),
        'domain': config.get('freshservice', 'domain', fallback='integotecllc.freshservice.com')
    }


def fetch_tickets_from_freshservice(api_key, domain, updated_since=None):
    """Fetch tickets from Freshservice API."""
    base_url = f"https://{domain}"
    auth_str = f"{api_key}:X"
    encoded_auth = base64.b64encode(auth_str.encode()).decode()
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Basic {encoded_auth}"
    }

    all_tickets = []
    page = 1
    per_page = 100

    print(f"Fetching tickets from Freshservice...")

    while True:
        params = {'page': page, 'per_page': per_page}
        if updated_since:
            params['updated_since'] = updated_since

        try:
            response = requests.get(
                f"{base_url}/api/v2/tickets",
                headers=headers,
                params=params,
                timeout=30
            )
            response.raise_for_status()

            data = response.json()
            tickets = data.get('tickets', [])

            if not tickets:
                break

            all_tickets.extend(tickets)
            print(f"  Fetched page {page}: {len(tickets)} tickets")
            page += 1

        except requests.exceptions.RequestException as e:
            print(f"Error fetching tickets: {e}", file=sys.stderr)
            break

    return all_tickets


def calculate_ticket_hours(ticket_id, api_key, domain):
    """Calculate total hours spent on a ticket from time entries."""
    base_url = f"https://{domain}"
    auth_str = f"{api_key}:X"
    encoded_auth = base64.b64encode(auth_str.encode()).decode()
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Basic {encoded_auth}"
    }

    try:
        response = requests.get(
            f"{base_url}/api/v2/tickets/{ticket_id}/time_entries",
            headers=headers,
            timeout=30
        )

        if response.status_code == 200:
            time_entries = response.json().get('time_entries', [])
            total_seconds = sum(entry.get('time_spent', 0) for entry in time_entries)
            return total_seconds / 3600.0  # Convert to hours
        else:
            return 0.0

    except requests.exceptions.RequestException:
        return 0.0


def get_company_account_number(department_ids, api_key, domain):
    """Get company account number from department ID."""
    # This would need to be enhanced to map department IDs to account numbers
    # For now, we'll return None if not found
    # In a real implementation, you'd query Codex or maintain a mapping
    return None


def sync_tickets_to_database(tickets, api_key, domain):
    """Sync tickets to the database."""
    print(f"\nSyncing {len(tickets)} tickets to database...")

    with app.app_context():
        synced = 0
        updated = 0

        for ticket in tickets:
            ticket_id = ticket.get('id')
            if not ticket_id:
                continue

            # Get or map account number (this needs to be implemented based on your mapping logic)
            # For now, we'll skip tickets without account numbers
            account_number = get_company_account_number(
                ticket.get('department_ids', []),
                api_key,
                domain
            )

            if not account_number:
                continue

            # Calculate total hours
            total_hours = calculate_ticket_hours(ticket_id, api_key, domain)

            # Check if ticket exists
            existing = TicketDetail.query.filter_by(ticket_id=ticket_id).first()

            if existing:
                # Update existing
                existing.subject = ticket.get('subject')
                existing.status = ticket.get('status_name')
                existing.priority = ticket.get('priority_name')
                existing.total_hours_spent = total_hours
                existing.last_updated_at = ticket.get('updated_at')
                updated += 1
            else:
                # Create new
                new_ticket = TicketDetail(
                    company_account_number=account_number,
                    ticket_id=ticket_id,
                    ticket_number=str(ticket.get('id')),
                    subject=ticket.get('subject'),
                    status=ticket.get('status_name'),
                    priority=ticket.get('priority_name'),
                    total_hours_spent=total_hours,
                    created_at=ticket.get('created_at'),
                    last_updated_at=ticket.get('updated_at')
                )
                db.session.add(new_ticket)
                synced += 1

        db.session.commit()
        print(f"✓ Synced {synced} new tickets, updated {updated} existing tickets")


def main():
    """Main execution."""
    print("="*60)
    print("HiveMatrix Ledger - Freshservice Ticket Sync")
    print("="*60)

    # Get credentials
    creds = get_freshservice_credentials()

    # Fetch tickets (optionally filter by updated_since)
    # For initial sync, fetch all from current year
    current_year_start = f"{datetime.now().year}-01-01T00:00:00Z"
    tickets = fetch_tickets_from_freshservice(
        creds['api_key'],
        creds['domain'],
        updated_since=current_year_start
    )

    print(f"\nFetched {len(tickets)} total tickets")

    # Sync to database
    if tickets:
        sync_tickets_to_database(tickets, creds['api_key'], creds['domain'])
    else:
        print("No tickets to sync.")

    print("\n" + "="*60)
    print("✓ Ticket sync complete!")
    print("="*60)


if __name__ == '__main__':
    main()
