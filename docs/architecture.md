# Architecture and data model

## Service ownership

| Component | Responsibility | Authoritative data |
|---|---|---|
| Vendor Portal | Internal customer, plan, license, installation, Ed25519 signing, vendor audit | Commercial/license control plane |
| Customer Portal | Tenant users, MFS operations UI, transaction/risk/review/catalog data | MFS intelligence plane |
| Kafka + risk worker | Durable real-time event transport and asynchronous scoring | Events are transport; PostgreSQL is the result store |
| Airflow | Scheduled discovery, quality, training, evaluation, aggregation and recovery | DAG/run state plus mirrored `DataPipeline` status |
| Ollama | Local intent selection and result explanation | No authoritative data; no SQL/write access |

The duplicate tracked tree at `vendor_portal/customer_portal/` is legacy repository debt. Runtime, tests, Docker, and new development use the root `customer_portal/`; the duplicate is deliberately untouched to avoid an unrelated destructive deletion.

## Runtime flow

1. A tenant API key authenticates `POST /api/v1/mfs/transactions/ingest/`.
2. Validation creates a normalized `Transaction` and idempotent `TransactionEvent` without logging the financial payload.
3. The event envelope is schema-checked and published to `mfs.transactions` with `acks=all`, retries, and an idempotent producer.
4. `consume_mfs_events` resolves the tenant and transaction, builds versioned features, and loads that tenant's active model artifact.
5. Logistic probability, Isolation Forest anomaly score, and deterministic rule score are combined into a 0–100 result.
6. Risk factors persist their source, contribution, feature evidence, model version, duration, event ID, and correlation ID.
7. A high-risk result creates a `FraudAlert` and `ReviewCase`, then emits risk and alert events.
8. A reviewer records APPROVE (legitimate/false positive), REJECT (confirmed risk), or ESCALATE. The decision creates a ground-truth label and audit event.

Duplicate event IDs return the original transaction. Reusing a transaction ID with a different event ID is rejected. Consumer failures go to `mfs.dead-letter`; failed database events can be reset by the Airflow recovery DAG.

## Tenant-aware domain model

Every operational record carries an `Organization` foreign key and every view/API query scopes by it.

- Parties and access: `MfsCustomer`, `Wallet`, `Account`, `Merchant`, `Agent`, `Device`, `MfsSession`, `Location`, `Beneficiary`, `IngestionAPIKey`.
- Transactions: `Transaction`, `TransactionEvent`.
- AI/risk: `ModelVersion`, `ModelPrediction`, `RiskAssessment`, `RiskFactor`, `TransactionLabel`.
- Operations: `FraudAlert`, `ReviewCase`, `ReviewDecision`, `MfsAuditEvent`.
- Data engineering: `DataSource`, `SchemaVersion`, `SchemaTable`, `SchemaColumn`, `DataPipeline`, `DataQualityMetric`.

Uniqueness constraints are tenant-composite (for example organization + transaction external ID). Customer-facing object lookups include the organization and return 404 for cross-tenant identifiers.

## Schema discovery

The connector supports PostgreSQL and read-only SQLite. Credentials are encrypted with Fernet before storage. Discovery captures schemas, tables, columns, types, nullability, primary keys, foreign keys, indexes, and row estimates/counts. A canonical SHA-256 fingerprint prevents duplicate versions. Each changed run records added/removed tables, added/removed columns, and type changes. Common PII column names are flagged for masking/governance.

PostgreSQL uses fixed catalog queries; SQLite uses fixed PRAGMA queries. User input is never converted into arbitrary SQL and the LLM is not part of this path.

## Risk decision

Feature version `v1` contains log amount, amount/average deviation, 10-minute velocity, new-beneficiary count, device/location changes, cyclical hour, merchant/agent history, and failed transactions in 24 hours.

```text
score = 100 × (0.55 × logistic probability
             + 0.25 × normalized anomaly score
             + 0.20 × normalized rule score)
```

Default bands are LOW `<40`, MEDIUM `40–69`, HIGH `≥70`; environment variables can change the thresholds. Rules create human-readable point factors. Positive standardized logistic contributions create model factors. Explanations are persisted from these actual contributions—not generated after the fact by an LLM.

## RBAC

| Role | Access |
|---|---|
| `ORG_ADMIN` | All tenant screens, connector creation, API-key issuance, reviews |
| `RISK_ANALYST` | Intelligence, alerts, reviews, catalog discovery, assistant, model monitoring |
| `REVIEWER` | Read intelligence and record review decisions |
| `VIEWER` | Read dashboards, transactions, alerts, schemas, and model status |

Vendor roles remain unchanged and separate: `SUPER_ADMIN`, `LICENSE_MANAGER`, `SUPPORT_AGENT`, and `VIEWER`.
