import base64
import json

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from django.conf import settings

KEY_PREFIX = "DSK1"

VENDOR_PUBLIC_KEY_B64 = "sDeNfpuuBjSPWNNrR+sHSR/oOhrTfAqGpjfEHRzDF4s="


class InvalidLicenseKey(Exception):
    pass


class SigningKeyNotConfigured(Exception):
    pass


def _b64encode(raw_bytes):
    return base64.urlsafe_b64encode(raw_bytes).decode().rstrip("=")


def _b64decode(text):
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + padding)


def _canonical_payload_bytes(payload):
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()


def sign_license_payload(payload):
    private_key_b64 = settings.LICENSE_SIGNING_PRIVATE_KEY_B64
    if not private_key_b64:
        raise SigningKeyNotConfigured(
            "LICENSE_SIGNING_PRIVATE_KEY_B64 is not set in the environment. "
            "This key must never be committed to source control."
        )

    private_key = Ed25519PrivateKey.from_private_bytes(base64.b64decode(private_key_b64))
    payload_bytes = _canonical_payload_bytes(payload)
    signature = private_key.sign(payload_bytes)
    return f"{KEY_PREFIX}.{_b64encode(payload_bytes)}.{_b64encode(signature)}"


def verify_license_key(license_key):
    license_key = (license_key or "").strip()
    parts = license_key.split(".")

    if len(parts) != 3 or parts[0] != KEY_PREFIX:
        raise InvalidLicenseKey("Malformed license key.")

    try:
        payload_bytes = _b64decode(parts[1])
        signature = _b64decode(parts[2])
        payload = json.loads(payload_bytes)
    except (ValueError, json.JSONDecodeError) as error:
        raise InvalidLicenseKey("Malformed license key.") from error

    public_key = Ed25519PublicKey.from_public_bytes(base64.b64decode(VENDOR_PUBLIC_KEY_B64))

    try:
        public_key.verify(signature, payload_bytes)
    except InvalidSignature as error:
        raise InvalidLicenseKey("License key signature is invalid.") from error

    required_fields = {"customer", "plan", "issued_at", "expires_at"}
    if not required_fields.issubset(payload):
        raise InvalidLicenseKey("License key is missing required fields.")

    return payload
