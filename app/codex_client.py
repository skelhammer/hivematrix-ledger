"""
Codex Integration Layer for Ledger Service

This module provides functions to fetch company, asset, and user data
from the Codex service for billing calculations.
"""

from app.service_client import call_service
from flask import current_app


def get_company_data(account_number):
    """
    Fetch company data from Codex by account number.

    Returns:
        dict: Company data or None if not found
    """
    try:
        response = call_service('codex', f'/api/companies/{account_number}')
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 404:
            return None
        else:
            current_app.logger.error(f"Failed to fetch company {account_number}: {response.status_code}")
            return None
    except Exception as e:
        current_app.logger.error(f"Error fetching company {account_number}: {e}")
        return None


def get_all_companies():
    """
    Fetch all companies from Codex.

    Returns:
        list: List of company dicts
    """
    try:
        response = call_service('codex', '/api/companies')
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 404:
            current_app.logger.warning("Codex /api/companies endpoint not found. Is Codex service running?")
            return []
        else:
            current_app.logger.error(f"Failed to fetch companies from Codex: HTTP {response.status_code}")
            return []
    except ConnectionError as e:
        current_app.logger.warning(f"Cannot connect to Codex service: {e}. Is it running on the configured URL?")
        return []
    except Exception as e:
        current_app.logger.error(f"Error fetching companies from Codex: {e}")
        return []


def get_all_companies_with_details(include_tickets=False, year=None):
    """
    Fetch all companies with their assets, contacts, locations, and optionally tickets in one bulk call.
    Optimized for dashboard - reduces API calls from 5N+1 to just 1.

    Args:
        include_tickets: If True, includes ticket data in response
        year: Optional year filter for tickets

    Returns:
        list: List of dicts with 'company', 'assets', 'contacts', 'locations', and optionally 'tickets' keys
    """
    try:
        endpoint = '/api/companies/bulk'
        params = []

        if include_tickets:
            params.append('include_tickets=true')
        if year:
            params.append(f'year={year}')

        if params:
            endpoint += '?' + '&'.join(params)

        response = call_service('codex', endpoint)
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 404:
            current_app.logger.warning("Codex /api/companies/bulk endpoint not found. Falling back to individual calls.")
            return None
        else:
            current_app.logger.error(f"Failed to fetch bulk companies from Codex: HTTP {response.status_code}")
            return None
    except ConnectionError as e:
        current_app.logger.warning(f"Cannot connect to Codex service: {e}. Is it running on the configured URL?")
        return None
    except Exception as e:
        current_app.logger.error(f"Error fetching bulk companies from Codex: {e}")
        return None


def get_company_assets(account_number):
    """
    Fetch all assets for a company from Codex.

    Returns:
        list: List of asset dicts
    """
    try:
        response = call_service('codex', f'/api/companies/{account_number}/assets')
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 404:
            return []
        else:
            current_app.logger.error(f"Failed to fetch assets for {account_number}: {response.status_code}")
            return []
    except Exception as e:
        current_app.logger.error(f"Error fetching assets for {account_number}: {e}")
        return []


def get_company_contacts(account_number):
    """
    Fetch all contacts/users for a company from Codex.

    Returns:
        list: List of contact/user dicts
    """
    try:
        response = call_service('codex', f'/api/companies/{account_number}/contacts')
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 404:
            return []
        else:
            current_app.logger.error(f"Failed to fetch contacts for {account_number}: {response.status_code}")
            return []
    except Exception as e:
        current_app.logger.error(f"Error fetching contacts for {account_number}: {e}")
        return []


def get_company_locations(account_number):
    """
    Fetch all locations for a company from Codex.

    Returns:
        list: List of location dicts
    """
    try:
        response = call_service('codex', f'/api/companies/{account_number}/locations')
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 404:
            return []
        else:
            current_app.logger.error(f"Failed to fetch locations for {account_number}: {response.status_code}")
            return []
    except Exception as e:
        current_app.logger.error(f"Error fetching locations for {account_number}: {e}")
        return []


def get_company_tickets(account_number, year=None):
    """
    Fetch all tickets for a company from Codex.

    Args:
        account_number: Company account number
        year: Optional year filter (e.g., 2025)

    Returns:
        list: List of ticket dicts
    """
    try:
        endpoint = f'/api/companies/{account_number}/tickets'
        if year:
            endpoint += f'?year={year}'

        response = call_service('codex', endpoint)
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 404:
            return []
        else:
            current_app.logger.error(f"Failed to fetch tickets for {account_number}: {response.status_code}")
            return []
    except Exception as e:
        current_app.logger.error(f"Error fetching tickets for {account_number}: {e}")
        return []


def get_billing_data_from_codex(account_number):
    """
    Fetch all necessary data from Codex for billing calculations.

    Returns:
        dict: {
            'company': company_data,
            'assets': assets_data,
            'users': users_data,
            'locations': locations_data,
            'tickets': tickets_data
        } or None if company not found
    """
    company = get_company_data(account_number)
    if not company:
        return None

    assets = get_company_assets(account_number)
    users = get_company_contacts(account_number)
    locations = get_company_locations(account_number)
    tickets = get_company_tickets(account_number)

    return {
        'company': company,
        'assets': assets,
        'users': users,
        'locations': locations,
        'tickets': tickets
    }
