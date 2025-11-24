"""
Codex Integration Layer for Ledger Service

This module provides functions to fetch company, asset, user, and billing plan data
from the Codex service for billing calculations.
"""

from app.service_client import call_service
from flask import current_app
import logging

logger = logging.getLogger(__name__)


# ===== COMPANY DATA FUNCTIONS =====

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


# ===== BILLING PLAN FUNCTIONS =====

class CodexBillingClient:
    """Client for fetching billing plan data from Codex."""

    @staticmethod
    def get_all_plans():
        """
        Fetch all billing plans from Codex.

        Returns:
            list: List of billing plan dictionaries, or empty list on error
        """
        try:
            response = call_service('codex', '/billing-plans/api/plans')

            if response.status_code == 200:
                data = response.json()
                return data.get('plans', [])
            else:
                logger.error(f"Failed to fetch plans from Codex: {response.status_code} - {response.text}")
                return []

        except Exception as e:
            logger.error(f"Error fetching plans from Codex: {e}")
            return []

    @staticmethod
    def get_plan(plan_name, term_length):
        """
        Fetch a specific billing plan from Codex.

        Args:
            plan_name: Name of the billing plan
            term_length: Term length (e.g., '1 Year', 'Month to Month')

        Returns:
            dict: Billing plan data, or None if not found
        """
        try:
            # URL encode the plan name and term length
            from urllib.parse import quote
            plan_name_encoded = quote(plan_name, safe='')
            term_length_encoded = quote(term_length, safe='')

            response = call_service('codex', f'/billing-plans/api/plans/{plan_name_encoded}/{term_length_encoded}')

            if response.status_code == 200:
                data = response.json()
                return data.get('plan')
            elif response.status_code == 404:
                logger.warning(f"Plan not found in Codex: {plan_name} ({term_length})")
                return None
            else:
                logger.error(f"Failed to fetch plan from Codex: {response.status_code} - {response.text}")
                return None

        except Exception as e:
            logger.error(f"Error fetching plan from Codex: {e}")
            return None

    @staticmethod
    def get_feature_options():
        """
        Fetch all feature options from Codex, grouped by category.

        Returns:
            dict: Feature options grouped by category, or empty dict on error
        """
        try:
            response = call_service('codex', '/billing-plans/api/feature-options')

            if response.status_code == 200:
                data = response.json()
                return data.get('features', {})
            else:
                logger.error(f"Failed to fetch feature options from Codex: {response.status_code} - {response.text}")
                return {}

        except Exception as e:
            logger.error(f"Error fetching feature options from Codex: {e}")
            return {}

    @staticmethod
    def get_feature_categories():
        """
        Fetch all feature categories from Codex.

        Returns:
            list: List of feature category names, or empty list on error
        """
        try:
            response = call_service('codex', '/billing-plans/api/feature-categories')

            if response.status_code == 200:
                data = response.json()
                return data.get('categories', [])
            else:
                logger.error(f"Failed to fetch feature categories from Codex: {response.status_code} - {response.text}")
                return []

        except Exception as e:
            logger.error(f"Error fetching feature categories from Codex: {e}")
            return []

    @staticmethod
    def get_plans_as_dict():
        """
        Fetch all plans and return as a dictionary keyed by (plan_name, term_length).

        Returns:
            dict: Plans keyed by (plan_name, term_length) tuple
        """
        plans = CodexBillingClient.get_all_plans()
        plans_dict = {}

        for plan in plans:
            key = (plan['plan_name'], plan['term_length'])
            plans_dict[key] = plan

        return plans_dict

    @staticmethod
    def get_plan_names():
        """
        Get list of unique plan names.

        Returns:
            list: Sorted list of unique plan names
        """
        plans = CodexBillingClient.get_all_plans()
        plan_names = set(plan['plan_name'] for plan in plans)
        return sorted(plan_names)

    @staticmethod
    def get_term_lengths_for_plan(plan_name):
        """
        Get available term lengths for a specific plan.

        Args:
            plan_name: Name of the billing plan

        Returns:
            list: List of term lengths available for this plan
        """
        plans = CodexBillingClient.get_all_plans()
        terms = [plan['term_length'] for plan in plans if plan['plan_name'] == plan_name]
        return sorted(terms)


# Legacy function aliases for backward compatibility
def get_billing_plan_from_codex(plan_name, term_length):
    """
    DEPRECATED: Use CodexBillingClient.get_plan() instead.
    Fetch billing plan details from Codex (includes features).
    """
    return CodexBillingClient.get_plan(plan_name, term_length)


def get_all_billing_plans_bulk():
    """
    DEPRECATED: Use CodexBillingClient.get_all_plans() instead.
    Fetch all unique billing plans with their features in one bulk call.
    """
    plans = CodexBillingClient.get_all_plans()
    # Convert to old format (dict keyed by "plan_name|term_length")
    plans_dict = {}
    for plan in plans:
        key = f"{plan['plan_name']}|{plan['term_length']}"
        plans_dict[key] = plan
    return plans_dict


def get_all_feature_options():
    """
    DEPRECATED: Use CodexBillingClient.get_feature_options() instead.
    Fetch all feature options from Codex.
    """
    return CodexBillingClient.get_feature_options()


# Convenience functions
def get_all_plans():
    """Get all billing plans from Codex."""
    return CodexBillingClient.get_all_plans()


def get_plan(plan_name, term_length):
    """Get a specific billing plan from Codex."""
    return CodexBillingClient.get_plan(plan_name, term_length)


def get_feature_options():
    """Get all feature options from Codex."""
    return CodexBillingClient.get_feature_options()


def get_feature_categories():
    """Get all feature categories from Codex."""
    return CodexBillingClient.get_feature_categories()
