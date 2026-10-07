import json
import logging
import atexit
from threading import Lock

from django.conf import settings
from kafka import KafkaConsumer, KafkaProducer

from .event_schemas import validate_event

logger = logging.getLogger(__name__)
_producer = None
_producer_lock = Lock()


def _security_config():
    config = {"security_protocol": settings.KAFKA_SECURITY_PROTOCOL}
    if settings.KAFKA_SECURITY_PROTOCOL.startswith("SASL"):
        config.update(sasl_mechanism=settings.KAFKA_SASL_MECHANISM,
                      sasl_plain_username=settings.KAFKA_SASL_USERNAME,
                      sasl_plain_password=settings.KAFKA_SASL_PASSWORD)
    return config


def producer():
    global _producer
    if _producer is None:
        with _producer_lock:
            if _producer is None:
                _producer = KafkaProducer(
                    bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS.split(","), client_id=settings.KAFKA_CLIENT_ID,
                    value_serializer=lambda value: json.dumps(value, separators=(",", ":")).encode(),
                    acks="all", retries=5, max_in_flight_requests_per_connection=1,
                    **_security_config(),
                )
    return _producer


def close_producer():
    global _producer
    if _producer is not None:
        _producer.close(timeout=5)
        _producer = None


atexit.register(close_producer)


def publish(topic, payload, key=None):
    transaction_topics = {settings.KAFKA_TOPIC_TRANSACTIONS, settings.KAFKA_TOPIC_RISK,
                          settings.KAFKA_TOPIC_ALERTS, settings.KAFKA_TOPIC_REVIEW}
    validate_event(payload, required=("transaction_id",) if topic in transaction_topics else ())
    result = producer().send(topic, value=payload, key=(key or payload.get("event_id", "")).encode()).get(timeout=10)
    return {"topic": result.topic, "partition": result.partition, "offset": result.offset}


def consumer(topic=None):
    return KafkaConsumer(
        topic or settings.KAFKA_TOPIC_TRANSACTIONS,
        bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS.split(","),
        group_id=settings.KAFKA_CONSUMER_GROUP, enable_auto_commit=False, auto_offset_reset="earliest",
        value_deserializer=lambda raw: json.loads(raw.decode()),
        **_security_config(),
    )


def event_envelope(event):
    tx = event.transaction
    return {
        "event_id": str(event.event_id), "event_type": event.event_type,
        "tenant_id": str(event.organization.external_id), "source": tx.source,
        "timestamp": event.occurred_at.isoformat(), "correlation_id": str(event.correlation_id),
        "schema_version": event.schema_version, "transaction_id": tx.external_id,
    }
