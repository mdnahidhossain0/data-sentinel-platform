import logging
import time

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class SentinelCloudError(Exception):
    """Base error for any failure talking to the Sentinel Cloud API."""


class SentinelCloudUnavailable(SentinelCloudError):
    """The API could not be reached at all (timeout, connection refused, DNS)."""


class SentinelCloudUnauthorized(SentinelCloudError):
    """The API rejected the account/secret pair."""


class SentinelCloudClient:
    def __init__(self, account_id, secret, base_url=None, timeout=None, max_retries=None):
        self.account_id = account_id
        self.secret = secret
        self.base_url = (base_url or settings.SENTINEL_CLOUD_URL).rstrip("/")
        self.timeout = timeout or settings.SENTINEL_CLOUD_TIMEOUT_SECONDS
        self.max_retries = max_retries if max_retries is not None else settings.SENTINEL_CLOUD_MAX_RETRIES

    def _headers(self):
        return {"X-Sentinel-Account": str(self.account_id), "X-Sentinel-Secret": self.secret}

    def _get(self, path):
        url = f"{self.base_url}{path}"
        last_error = None

        for attempt in range(self.max_retries + 1):
            try:
                response = requests.get(url, headers=self._headers(), timeout=self.timeout)
            except requests.Timeout as error:
                last_error = error
                logger.warning("Sentinel Cloud request timed out (attempt %s): %s", attempt + 1, url)
            except requests.RequestException as error:
                last_error = error
                logger.warning("Sentinel Cloud request failed (attempt %s): %s", attempt + 1, error)
            else:
                if response.status_code == 401:
                    raise SentinelCloudUnauthorized("Invalid account ID or secret.")
                if response.status_code == 429:
                    time.sleep(min(2**attempt, 5))
                    continue
                try:
                    response.raise_for_status()
                except requests.HTTPError as error:
                    logger.error(
                        "Sentinel Cloud API returned HTTP %s for %s",
                        response.status_code,
                        url,
                    )
                    raise SentinelCloudUnavailable(
                        f"Sentinel Cloud returned HTTP {response.status_code}."
                    ) from error
                return response.json()

            if attempt < self.max_retries:
                time.sleep(min(2**attempt, 5))

        raise SentinelCloudUnavailable(f"Could not reach Sentinel Cloud after {self.max_retries + 1} attempt(s).") from last_error

    def get_partner_status(self):
        return self._get("/api/v1/partner/status/")


def get_client_for_organization(organization):
    if not organization or not organization.is_linked:
        return None
    return SentinelCloudClient(account_id=organization.external_id, secret=organization.api_secret)
