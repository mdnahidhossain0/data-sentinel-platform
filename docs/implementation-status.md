# Implementation status

## Implemented

- Existing Vendor/Customer licensing, provisioning, Ed25519, RBAC, tenant isolation, audit, and acceptance tests are preserved.
- Tenant-scoped normalized MFS entities, event idempotency, hashed API keys, encrypted connector credentials, PostgreSQL/SQLite schema discovery, version fingerprints, schema diffs, and explorer UI.
- Kafka producer/consumer integration, explicit topic creation, validated v1 envelopes, risk/alert/review publication, retry configuration, and dead-letter routing.
- Actual synthetic-data training with logistic regression + Isolation Forest; persisted artifacts, parameters, dataset/feature versions, measured metrics, predictions, and explanations.
- Real authenticated inference API, hybrid risk aggregation, alert statuses, review queue/decision audit, outcome labels, false-positive/false-negative monitoring, and tenant dashboards.
- Local Ollama/Qwen integration through four approved read-only tools with permission checks and unsafe-tool rejection.
- Ten Airflow DAG definitions, Redis shared rate limiting, retention command, correlation IDs, local Docker stack, demo source database, and Kafka-based demo command.
- Persisted, tenant-scoped business KPI snapshots calculated from transactions, assessments, alerts, reviews, and decisions. The dashboard exposes scoring coverage, detection/review latency, review completion, false-positive and override rates, confirmed-risk counts, and confirmed-risk transaction value without presenting that value as prevented loss.
- A reproducible Locust mixed-workload harness, Nginx `least_conn` gateway, configurable Gunicorn concurrency, persistent database connections, independently scalable web and Kafka worker services, deterministic load-test tenant bootstrap, and captured CSV/HTML evidence.

## Partially implemented

- Historical backfill and feature-dataset Airflow tasks currently provide controlled hooks and inventories; production source-specific field mappings and a durable feature store are deployment work.
- Pipeline dashboard shows persisted processed/failed event counts, not broker-derived consumer-lag telemetry.
- Alerts are persisted, visible in the UI, and emitted to Kafka; email/SMS/case-management destinations are not configured.
- Local Compose uses plaintext Kafka and local environment secrets. Client settings support SASL/TLS, but certificates, broker ACLs, and a secret manager are deployment-specific.
- False negatives are measured only when an external or human label exists. High-risk review naturally produces more positive-prediction labels than low-risk labels.
- PII identification is name-based and masking is implemented for selected fields; a full policy engine and jurisdiction-specific retention matrix are not included.
- Compose proves horizontal application/worker scaling on one Docker host. Multi-host orchestration, database/Kafka high availability, autoscaling, and a formal production capacity target remain deployment work.

## Roadmap

- Source-specific CDC/connectors (for example Debezium) and validated mapping UI for arbitrary MFS schemas.
- Durable feature store, drift monitoring, champion/challenger promotion gates, calibration, SHAP where justified, and training on approved real labels.
- Prometheus/OpenTelemetry metrics, broker consumer lag, distributed tracing, SIEM export, paging integrations, and SLOs.
- External alert delivery, maker-checker review controls, sampled low-risk labeling, and formal model-risk/governance approval.
- Kubernetes/managed-service deployment, KMS/Vault integration, disaster recovery, autoscaling, multi-broker Kafka, database replicas, and compliance evidence.
- Remove the legacy duplicate `vendor_portal/customer_portal/` tree after repository-owner confirmation.
