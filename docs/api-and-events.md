# APIs and Kafka event contracts

## Authentication

MFS machine APIs require `Authorization: Bearer dsk_...`. Keys are tenant scoped, shown once, and stored as a prefix plus SHA-256 digest. The default limit is 600 requests/minute/key; Docker uses Redis so the limit is shared by web workers.

## Ingest a transaction

`POST /api/v1/mfs/transactions/ingest/`

```json
{
  "event_id": "6bd5f036-3bd2-4f11-8190-e5f5966c2bb2",
  "transaction_id": "TX-10001",
  "customer_id": "CUS-100",
  "amount": 85000,
  "currency": "BDT",
  "occurred_at": "2026-10-07T09:30:00+06:00",
  "status": "SUCCESS",
  "historical_average_amount": 3200,
  "device_changed": true,
  "location_changed": true,
  "transactions_last_10_min": 17,
  "new_beneficiaries": 6
}
```

Success is `202 Accepted` with event and transaction IDs. A repeated event ID is `200` with `status=duplicate`; a conflicting transaction ID is `400`; unavailable Kafka is `503` and the stored event is marked failed for recovery.

## Synchronous inference

`POST /api/v1/risk/predict/` accepts the same payload and returns:

```json
{
  "transaction_id": "TX-10001",
  "risk_score": 91,
  "risk_level": "HIGH",
  "fraud_probability": 0.87,
  "decision": "REVIEW",
  "model_version": "v20261007093000",
  "explanation": "Unusual transaction amount; High transaction velocity; New or changed device",
  "factors": [{"label": "High transaction velocity", "contribution": 24, "source": "RULE"}],
  "correlation_id": "f9753e5b-3b3f-43ca-a72f-5901b1a4860d"
}
```

The numeric values above illustrate the wire shape; the running model produces the actual values. If no active artifact exists, the endpoint returns `503` instead of fabricating a score.

## Common Kafka envelope

All topic payloads use schema version `1.0` and require:

```json
{
  "event_id": "UUID",
  "event_type": "transaction.created",
  "tenant_id": "tenant UUID",
  "source": "api",
  "timestamp": "ISO-8601",
  "correlation_id": "UUID",
  "schema_version": "1.0",
  "transaction_id": "TX-10001"
}
```

The transaction event contains identifiers, not raw amounts, phone numbers, credentials, or customer PII. The worker retrieves the tenant-scoped record from PostgreSQL.

| Topic | Producer | Consumer/purpose |
|---|---|---|
| `mfs.transactions` | ingestion API/demo | risk worker |
| `mfs.transaction.risk` | risk worker | analytics/dashboard integrations |
| `mfs.transaction.alerts` | risk worker | alert integrations |
| `mfs.review.events` | review/demo workflow | model-feedback integrations |
| `mfs.schema.events` | schema pipeline integration point | catalog/monitoring |
| `mfs.data-quality.events` | quality pipeline integration point | monitoring |
| `mfs.dead-letter` | risk worker | operator recovery |

Producer settings use `acks=all`, retries, and idempotence. Consumers commit only after processing or deliberate DLQ routing. The local stack uses three partitions and one replica; production must use multiple brokers/replicas and TLS/SASL ACLs.
