from unittest.mock import Mock, patch

import requests
from django.test import TestCase, override_settings

from .client import SentinelCloudClient, SentinelCloudUnauthorized, SentinelCloudUnavailable


@override_settings(SENTINEL_CLOUD_TIMEOUT_SECONDS=1, SENTINEL_CLOUD_MAX_RETRIES=1)
class SentinelCloudClientTests(TestCase):
    def setUp(self):
        self.client = SentinelCloudClient(account_id="abc-123", secret="s3cr3t", base_url="http://cloud.test")

    @patch("api_client.client.requests.get")
    def test_successful_response_is_parsed(self, mock_get):
        mock_response = Mock(status_code=200)
        mock_response.json.return_value = {"license": {"status": "ACTIVE"}}
        mock_get.return_value = mock_response

        result = self.client.get_partner_status()
        self.assertEqual(result["license"]["status"], "ACTIVE")

        headers = mock_get.call_args.kwargs["headers"]
        self.assertEqual(headers["X-Sentinel-Account"], "abc-123")
        self.assertEqual(headers["X-Sentinel-Secret"], "s3cr3t")

    @patch("api_client.client.requests.get")
    def test_401_raises_unauthorized(self, mock_get):
        mock_get.return_value = Mock(status_code=401)
        with self.assertRaises(SentinelCloudUnauthorized):
            self.client.get_partner_status()

    @patch("api_client.client.requests.get")
    def test_timeout_retries_then_raises_unavailable(self, mock_get):
        mock_get.side_effect = requests.Timeout("timed out")
        with self.assertRaises(SentinelCloudUnavailable):
            self.client.get_partner_status()
        self.assertEqual(mock_get.call_count, 2)  # initial attempt + 1 retry

    @patch("api_client.client.requests.get")
    def test_connection_error_raises_unavailable(self, mock_get):
        mock_get.side_effect = requests.ConnectionError("refused")
        with self.assertRaises(SentinelCloudUnavailable):
            self.client.get_partner_status()
