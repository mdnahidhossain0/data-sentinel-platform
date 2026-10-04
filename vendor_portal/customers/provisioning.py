import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class ProvisioningError(Exception):
    """Raised when the Customer Portal could not be provisioned/updated."""


def _headers():
    return {"X-Vendor-Provisioning-Key": settings.VENDOR_PROVISIONING_KEY}


def provision_customer_account(customer, email, password, raw_api_secret, organization_name=None):
    """Create (or fully re-provision) a customer's Customer Portal login.

    Called right after customer.set_api_secret() (which is the only moment
    the plaintext secret exists), and any time the vendor issues a new
    temporary password. Requires email, password, and the just-generated secret.
    """
    payload = {
        "external_id": str(customer.external_id),
        "api_secret": raw_api_secret,
        "email": email,
        "password": password,
        "organization_name": organization_name or customer.company_name,
        "status": customer.status,
    }
    return _post(payload)


def push_status_update(customer):
    """Push only the account-status change (suspend/reactivate/archive).

    No password or secret is sent - the Customer Portal already has the
    secret from the original provisioning call, and this never touches the
    customer's existing password. It only flips whether they can log in.
    """
    payload = {
        "external_id": str(customer.external_id),
        "organization_name": customer.company_name,
        "status": customer.status,
    }
    return _post(payload)


def push_secret_rotation(customer, raw_api_secret):
    """Rotate just the Cloud API secret on an existing account, leaving the
    customer's Customer Portal password untouched. Use this (not a bare local
    set_api_secret()) any time the secret is regenerated, or the Customer
    Portal silently keeps authenticating with the old one until it's told.
    """
    payload = {
        "external_id": str(customer.external_id),
        "api_secret": raw_api_secret,
        "organization_name": customer.company_name,
        "status": customer.status,
    }
    return _post(payload)


def _post(payload):
    url = f"{settings.CUSTOMER_PORTAL_URL.rstrip('/')}/internal/provision/"
    try:
        response = requests.post(url, json=payload, headers=_headers(), timeout=5)
    except requests.RequestException as error:
        logger.warning("Customer Portal provisioning call failed: %s", error)
        raise ProvisioningError(f"Could not reach the Customer Portal: {error}") from error

    if response.status_code != 200:
        logger.warning("Customer Portal rejected provisioning call: %s %s", response.status_code, response.text)
        raise ProvisioningError(f"Customer Portal rejected the request ({response.status_code}).")

    return response.json()
