import json
import logging

from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .audit import audit
from .auth import authenticate_api_key
from .risk import assess_transaction
from .services import ValidationError, ingest_transaction
from .streaming import event_envelope, publish

logger = logging.getLogger(__name__)


def _limited(key):
    cache_key = f"mfs-api:{key.pk}"
    if cache.add(cache_key, 1, 60):
        return False
    try:
        return cache.incr(cache_key) > settings.MFS_API_RATE_LIMIT_PER_MINUTE
    except ValueError:
        cache.set(cache_key, 1, 60)
        return False


def _body(request):
    try:
        return json.loads(request.body or "{}")
    except json.JSONDecodeError as error:
        raise ValidationError("invalid JSON body") from error


@csrf_exempt
@require_POST
def ingest(request):
    key = authenticate_api_key(request)
    if not key: return JsonResponse({"error": "unauthorized"}, status=401)
    if _limited(key): return JsonResponse({"error": "rate limit exceeded"}, status=429)
    try:
        transaction, event, created = ingest_transaction(key.organization, _body(request))
    except ValidationError as error:
        return JsonResponse({"error": str(error)}, status=400)
    if not created:
        return JsonResponse({"status": "duplicate", "event_id": str(event.event_id), "transaction_id": transaction.external_id})
    try:
        metadata = publish(settings.KAFKA_TOPIC_TRANSACTIONS, event_envelope(event))
    except Exception as error:
        event.status, event.error_code = event.STATUS_FAILED, "KAFKA_UNAVAILABLE"
        event.save(update_fields=["status", "error_code", "updated_at"])
        logger.warning("Kafka publish failed for event_id=%s error=%s", event.event_id, error.__class__.__name__)
        return JsonResponse({"error": "stream unavailable", "event_id": str(event.event_id)}, status=503)
    event.status = event.STATUS_PUBLISHED
    event.save(update_fields=["status", "updated_at"])
    audit("transaction.ingested", organization=key.organization, target=transaction, correlation_id=transaction.correlation_id,
          metadata={"event_id": str(event.event_id), "topic": metadata["topic"]})
    return JsonResponse({"status": "accepted", "event_id": str(event.event_id), "transaction_id": transaction.external_id}, status=202)


@csrf_exempt
@require_POST
def predict(request):
    key = authenticate_api_key(request)
    if not key: return JsonResponse({"error": "unauthorized"}, status=401)
    if _limited(key): return JsonResponse({"error": "rate limit exceeded"}, status=429)
    try:
        transaction, event, _ = ingest_transaction(key.organization, _body(request))
        assessment = transaction.risk_assessments.first() or assess_transaction(transaction)
    except ValidationError as error:
        return JsonResponse({"error": str(error)}, status=400)
    except (RuntimeError, FileNotFoundError) as error:
        return JsonResponse({"error": str(error)}, status=503)
    event.status = event.STATUS_PROCESSED
    event.save(update_fields=["status", "updated_at"])
    return JsonResponse({
        "transaction_id": transaction.external_id, "risk_score": assessment.score, "risk_level": assessment.level,
        "fraud_probability": round(assessment.fraud_probability, 6), "decision": assessment.decision,
        "model_version": assessment.model_version.version, "explanation": assessment.explanation,
        "factors": [{"label": f.label, "contribution": f.contribution, "source": f.source} for f in assessment.factors.all()],
        "correlation_id": str(transaction.correlation_id),
    })
