# Operations, Airflow, ML, and demo runbook

## Environment variables

| Variable | Purpose |
|---|---|
| `DATA_SOURCE_ENCRYPTION_KEY` | Required Fernet key for connector secrets |
| `KAFKA_BOOTSTRAP_SERVERS` | Broker list |
| `KAFKA_SECURITY_PROTOCOL`, `KAFKA_SASL_*` | Production TLS/SASL client settings |
| `MODEL_ARTIFACT_DIR` | Shared model artifact volume |
| `OLLAMA_BASE_URL`, `OLLAMA_MODEL` | Local inference endpoint/model |
| `MFS_HIGH_RISK_THRESHOLD`, `MFS_MEDIUM_RISK_THRESHOLD` | Decision bands |
| `MFS_RETENTION_DAYS` | Transaction retention default |
| `MFS_API_RATE_LIMIT_PER_MINUTE` | Per-key shared rate limit |
| `REDIS_URL` | Shared cache/rate limiter |
| `DB_CONN_MAX_AGE` | Persistent database connection lifetime in seconds |
| `CUSTOMER_WEB_WORKERS`, `CUSTOMER_WEB_THREADS` | Per-container Gunicorn concurrency |
| `LOADTEST_ADMIN_PASSWORD` | Local load-test tenant administrator password (12+ characters) |
| `LOADTEST_USERS`, `LOADTEST_SPAWN_RATE`, `LOADTEST_DURATION` | Headless Locust workload shape |

Existing Vendor/Customer variables remain documented in each portal's `.env.example`.

## Airflow DAGs

| DAG | Schedule | Operation |
|---|---|---|
| `mfs_ingestion_validation` | every 10 min | event failure metric |
| `mfs_data_quality` | hourly | invalid transaction metric |
| `mfs_historical_backfill` | manual | controlled backfill hook and eligible-row inventory |
| `mfs_feature_dataset` | daily | feature-preparation hook and eligible-row inventory |
| `mfs_model_training` | weekly | train and activate tenant models |
| `mfs_model_evaluation` | weekly | surface stored test metrics |
| `mfs_schema_change_detection` | hourly | discover and diff all sources |
| `mfs_analytics_aggregation` | every 15 min | aggregate operational KPIs |
| `mfs_risk_report` | daily | persist report run metrics |
| `mfs_failed_pipeline_recovery` | every 5 min | reset failed events for retry |

DAGs start paused so an operator can inspect configuration before enabling schedules. Each task invokes an idempotent Django management operation and mirrors outcome/counts into `DataPipeline`/`DataQualityMetric`.

`mfs_risk_report` also persists a `BusinessKPISnapshot`, which makes the reporting period, calculated metrics, generation time, and synthetic-data status auditable.

## Model training and measured prototype result

```bash
docker compose exec customer-web python manage.py train_risk_model --organization 1 --rows 8000 --seed 42
```

The training workflow uses a 75/25 stratified split, standardized logistic regression for explainability, and Isolation Forest for anomaly scoring. It persists dataset version, feature version, parameters, timestamp, artifact path, split sizes, confusion matrix, precision, recall, F1, ROC-AUC, and false-positive rate.

Reproduced on the deterministic **synthetic** dataset (`8,000` rows, seed `42`; 6,000 train / 2,000 test):

| Metric | Value |
|---|---:|
| Precision | 0.576560 |
| Recall | 0.745721 |
| F1 | 0.650320 |
| ROC-AUC | 0.875298 |
| False-positive rate | 0.140792 |
| Confusion matrix | `[[1367, 224], [104, 305]]` |

These are measured prototype results on generated data, not claims about production fraud detection. The UI labels them as synthetic. Human decisions populate `TransactionLabel`; the model-monitoring page separately computes observed precision, recall, false positives, false negatives, and FPR from available review labels.

## Demo flow

1. Start Docker, provision a customer, and sign into the Customer Portal.
2. Connect the bundled source database and run schema discovery.
3. Train the tenant model and issue an ingestion key.
4. Ensure `risk-worker` is healthy: `docker compose logs -f risk-worker`.
5. Run `demo_mfs_flow` from the root README. It publishes a deliberately high-risk synthetic event to Kafka, waits for asynchronous scoring, verifies alert/review creation, records a chosen reviewer decision, creates a label/audit event, and emits `mfs.review.events`.
6. Inspect `/mfs/`, `/mfs/alerts/`, `/mfs/reviews/`, `/mfs/models/`, and the Airflow DAG grid.

## Local AI assistant

Start the `llm` profile, then ask: “Show the top 10 high-risk merchants in the last hour and explain why.” Qwen returns only a tool name and bounded arguments. The server rejects tools outside the allowlist, runs an ORM query already scoped to the signed-in organization, and asks the local model to summarize only the validated JSON result. Every successful tool invocation is audited.

## Maintenance

```bash
docker compose exec customer-web python manage.py mfs_pipeline data_quality
docker compose exec customer-web python manage.py discover_mfs_schema
docker compose exec customer-web python manage.py purge_mfs_data --dry-run
docker compose exec customer-web python manage.py purge_mfs_data --days 365
docker compose logs -f customer-web risk-worker airflow-scheduler
```

## Capacity verification

Start more than one stateless web process and risk consumer behind the gateway:

```bash
docker compose up -d --build --scale customer-web=2 --scale risk-worker=3
docker compose ps
```

Bootstrap an isolated load-test tenant, then run the mixed workload. Keep the printed API key in the shell only; do not commit it.

```bash
docker compose exec -T customer-web python manage.py bootstrap_load_test --reset-data
MFS_API_KEY='<bootstrap output>' docker compose --profile loadtest run --rm load-tester
```

The workload sends 70% asynchronous Kafka ingestion, 20% synchronous low-risk scoring, and 10% synchronous high-risk scoring. Results are written to `artifacts/loadtest/`. Acceptance requires zero unexpected HTTP failures, healthy replicas after the run, and Kafka consumer lag returning toward zero. See [the scalability runbook](scalability.md) for interpretation and limitations.
