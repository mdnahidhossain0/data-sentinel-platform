import math

from django.utils import timezone


FEATURE_NAMES = [
    "log_amount", "amount_deviation", "velocity_10m", "new_beneficiaries",
    "device_changed", "location_changed", "hour_sin", "hour_cos",
    "merchant_risk", "agent_risk", "failed_24h",
]


def transaction_features(transaction):
    amount = float(transaction.amount)
    average = max(float(transaction.historical_average_amount), 1.0)
    hour = transaction.occurred_at.hour
    failed_24h = transaction.customer.transactions.filter(
        status="FAILED", occurred_at__gte=timezone.now() - timezone.timedelta(hours=24)
    ).exclude(pk=transaction.pk).count()
    values = {
        "log_amount": math.log1p(max(amount, 0)),
        "amount_deviation": amount / average,
        "velocity_10m": transaction.transactions_last_10_min,
        "new_beneficiaries": transaction.new_beneficiaries,
        "device_changed": int(transaction.device_changed),
        "location_changed": int(transaction.location_changed),
        "hour_sin": math.sin(2 * math.pi * hour / 24),
        "hour_cos": math.cos(2 * math.pi * hour / 24),
        "merchant_risk": transaction.merchant.historical_risk if transaction.merchant else 0.0,
        "agent_risk": transaction.agent.historical_risk if transaction.agent else 0.0,
        "failed_24h": failed_24h,
    }
    return values


def feature_vector(values):
    return [[float(values[name]) for name in FEATURE_NAMES]]
