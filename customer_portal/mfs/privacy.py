import hashlib
import re


def stable_hash(value):
    return hashlib.sha256(str(value).encode()).hexdigest()


def mask_phone(value):
    digits = re.sub(r"\D", "", value or "")
    return f"***{digits[-4:]}" if digits else ""


def redact_mapping(data):
    sensitive = {"phone", "email", "national_id", "password", "secret", "token", "api_key"}
    return {key: "[REDACTED]" if key.lower() in sensitive else value for key, value in data.items()}
