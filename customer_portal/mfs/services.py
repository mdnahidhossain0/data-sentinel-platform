import uuid
import logging
from decimal import Decimal, InvalidOperation

from django.db import transaction as db_transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .audit import audit
from .models import (
    Account, Agent, Beneficiary, Device, FraudAlert, Location, Merchant, MfsCustomer,
    ReviewDecision, Transaction, TransactionEvent, TransactionLabel, Wallet,
)
from .privacy import mask_phone


class ValidationError(Exception):
    pass


logger = logging.getLogger(__name__)


@db_transaction.atomic
def ingest_transaction(organization, payload):
    required = {"transaction_id", "customer_id", "amount", "occurred_at"}
    missing = sorted(required - payload.keys())
    if missing:
        raise ValidationError(f"Missing required fields: {', '.join(missing)}")
    try:
        amount = Decimal(str(payload["amount"]))
    except InvalidOperation as error:
        raise ValidationError("amount must be numeric") from error
    if amount < 0:
        raise ValidationError("amount must not be negative")
    occurred_at = parse_datetime(str(payload["occurred_at"]))
    if not occurred_at or timezone.is_naive(occurred_at):
        raise ValidationError("occurred_at must be an ISO-8601 timestamp with timezone")
    status = str(payload.get("status", "PENDING")).upper()
    if status not in {Transaction.STATUS_PENDING, Transaction.STATUS_SUCCESS, Transaction.STATUS_FAILED}:
        raise ValidationError("status must be PENDING, SUCCESS, or FAILED")
    event_id = payload.get("event_id") or uuid.uuid4()
    try:
        event_id = uuid.UUID(str(event_id))
    except ValueError as error:
        raise ValidationError("event_id must be a UUID") from error
    existing = TransactionEvent.objects.select_related("transaction").filter(organization=organization, event_id=event_id).first()
    if existing:
        return existing.transaction, existing, False
    transaction_id = str(payload["transaction_id"]).strip()
    customer_id = str(payload["customer_id"]).strip()
    if not transaction_id or len(transaction_id) > 100 or not customer_id or len(customer_id) > 100:
        raise ValidationError("transaction_id and customer_id must be 1-100 characters")
    customer, _ = MfsCustomer.objects.get_or_create(
        organization=organization, external_id=customer_id,
        defaults={"display_name": payload.get("customer_name", ""), "phone_masked": mask_phone(payload.get("phone", ""))},
    )
    merchant = agent = device = location = beneficiary = wallet = account = None
    if payload.get("merchant_id"):
        merchant, _ = Merchant.objects.get_or_create(organization=organization, external_id=str(payload["merchant_id"])[:100],
                                                      defaults={"name": str(payload.get("merchant_name", payload["merchant_id"]))[:255]})
    if payload.get("agent_id"):
        agent, _ = Agent.objects.get_or_create(organization=organization, external_id=str(payload["agent_id"])[:100],
                                                defaults={"name": str(payload.get("agent_name", payload["agent_id"]))[:255]})
    if payload.get("device_id"):
        device, _ = Device.objects.get_or_create(organization=organization, external_id=str(payload["device_id"])[:100],
                                                  defaults={"customer": customer, "first_seen_at": occurred_at})
        device.last_seen_at = occurred_at; device.save(update_fields=["last_seen_at", "updated_at"])
    if payload.get("location_id"):
        location, _ = Location.objects.get_or_create(organization=organization, external_id=str(payload["location_id"])[:100],
                                                      defaults={"country_code": str(payload.get("country_code", ""))[:2],
                                                                "region": str(payload.get("region", ""))[:100]})
    if payload.get("beneficiary_id"):
        beneficiary, _ = Beneficiary.objects.get_or_create(organization=organization, external_id=str(payload["beneficiary_id"])[:100],
                                                            defaults={"customer": customer, "first_seen_at": occurred_at})
    if payload.get("wallet_id"):
        wallet, _ = Wallet.objects.get_or_create(organization=organization, external_id=str(payload["wallet_id"])[:100],
                                                  defaults={"customer": customer})
    if payload.get("account_id"):
        account, _ = Account.objects.get_or_create(organization=organization, external_id=str(payload["account_id"])[:100],
                                                    defaults={"customer": customer})
    try:
        correlation_id = uuid.UUID(str(payload.get("correlation_id") or uuid.uuid4()))
        velocity = max(0, int(payload.get("transactions_last_10_min", 0)))
        new_beneficiaries = max(0, int(payload.get("new_beneficiaries", 0)))
        historical_average = Decimal(str(payload.get("historical_average_amount", 0)))
    except (ValueError, InvalidOperation) as error:
        raise ValidationError("correlation_id, counters, or historical average are invalid") from error
    tx, created = Transaction.objects.get_or_create(
        organization=organization, external_id=transaction_id,
        defaults={
            "customer": customer, "amount": amount, "currency": str(payload.get("currency", "BDT")).upper()[:3],
            "transaction_type": str(payload.get("transaction_type", "TRANSFER"))[:32],
            "status": status, "occurred_at": occurred_at, "merchant": merchant, "agent": agent,
            "device": device, "location": location, "beneficiary": beneficiary, "wallet": wallet, "account": account,
            "source": str(payload.get("source", "api"))[:100], "correlation_id": correlation_id,
            "device_changed": bool(payload.get("device_changed", False)),
            "location_changed": bool(payload.get("location_changed", False)),
            "transactions_last_10_min": velocity, "new_beneficiaries": new_beneficiaries,
            "historical_average_amount": historical_average,
        },
    )
    if not created:
        raise ValidationError("transaction_id already exists with a different event_id")
    event = TransactionEvent.objects.create(
        organization=organization, event_id=event_id, transaction=tx,
        correlation_id=tx.correlation_id, occurred_at=occurred_at,
    )
    return tx, event, True


@db_transaction.atomic
def record_review_decision(case, reviewer, decision_code, reason, comments=""):
    if case.status == "CLOSED":
        raise ValidationError("review case is already closed")
    decision = ReviewDecision.objects.create(
        organization=case.organization, review_case=case, reviewer=reviewer, decision=decision_code,
        reason=reason, comments=comments, risk_score=case.alert.assessment.score,
        model_version=case.alert.assessment.model_version.version if case.alert.assessment.model_version else "",
        evidence={"factor_ids": list(case.alert.assessment.factors.values_list("id", flat=True))},
    )
    TransactionLabel.objects.update_or_create(
        organization=case.organization, transaction=case.alert.assessment.transaction,
        defaults={"is_fraud": decision_code == ReviewDecision.DECISION_REJECT,
                  "source": "HUMAN_REVIEW", "labeled_by": reviewer, "notes": reason},
    )
    if decision_code == ReviewDecision.DECISION_APPROVE:
        case.alert.status = FraudAlert.STATUS_FALSE_POSITIVE
    elif decision_code == ReviewDecision.DECISION_REJECT:
        case.alert.status = FraudAlert.STATUS_CONFIRMED_RISK
    else:
        case.alert.status = FraudAlert.STATUS_ESCALATED
    case.alert.save(update_fields=["status", "updated_at"])
    case.status = "CLOSED" if decision_code != ReviewDecision.DECISION_ESCALATE else "ESCALATED"
    case.closed_at = timezone.now() if case.status == "CLOSED" else None
    case.save(update_fields=["status", "closed_at", "updated_at"])
    audit("review.decided", organization=case.organization, actor=reviewer, target=case,
          correlation_id=case.alert.assessment.transaction.correlation_id, metadata={"decision": decision_code, "reason": reason})

    def publish_review_event():
        try:
            from django.conf import settings
            from .streaming import publish
            tx = case.alert.assessment.transaction
            publish(settings.KAFKA_TOPIC_REVIEW, {
                "event_id": str(uuid.uuid4()), "event_type": "review.decided",
                "tenant_id": str(case.organization.external_id), "source": "review-service",
                "timestamp": timezone.now().isoformat(), "correlation_id": str(tx.correlation_id),
                "schema_version": "1.0", "transaction_id": tx.external_id, "decision": decision_code,
            })
        except Exception as error:
            logger.warning("Review event publish failed case_id=%s error=%s", case.pk, error.__class__.__name__)
    db_transaction.on_commit(publish_review_event)
    return decision
