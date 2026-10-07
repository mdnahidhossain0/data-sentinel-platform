# Scalability design and load-test evidence

## What scales

- Nginx publishes the single customer endpoint and distributes requests with `least_conn` across DNS-resolved `customer-web` replicas.
- Each web replica runs configurable Gunicorn workers and threads, uses database connection reuse/health checks, and stores rate-limit state in Redis rather than process memory.
- Kafka decouples ingestion from scoring. `risk-worker` replicas share one consumer group, so Kafka partitions distribute work without duplicate processing; transaction external IDs and event IDs provide idempotency.
- Database migrations run once in `customer-migrate`, avoiding concurrent migration races when the web tier is scaled.

This Compose topology demonstrates process-level horizontal scaling on one host. It does not by itself prove multi-host failover, unlimited throughput, or a production service-level objective. Those require representative production hardware/data, managed or replicated stateful services, and an agreed capacity target.

## Reproduce the test

```bash
docker compose up -d --build --scale customer-web=2 --scale risk-worker=3
docker compose exec -T customer-web python manage.py bootstrap_load_test --reset-data
MFS_API_KEY='<bootstrap output>' docker compose --profile loadtest run --rm load-tester
docker compose ps
docker compose exec -T kafka /opt/kafka/bin/kafka-consumer-groups.sh \
  --bootstrap-server kafka:9092 --describe --group data-sentinel-risk-v1
docker stats --no-stream
```

Locust writes an interactive report and machine-readable CSV files under `artifacts/loadtest/`. The aggregate CSV is the primary repeatable evidence; record the Docker host resources and test settings alongside any number quoted from it.

## Acceptance checks

1. Gateway, both web replicas, PostgreSQL, Redis, and Kafka remain healthy throughout the run.
2. Locust reports no unexpected response codes or contract failures.
3. Synchronous prediction latency is reviewed separately from asynchronous ingestion latency.
4. Consumer lag returns toward zero after traffic stops; a growing lag means worker capacity or partition count is insufficient.
5. Business KPI snapshots still reconcile with persisted transactions after the run.

## Verified local baseline — 2026-10-07

The repository's default local profile was exercised on Docker Desktop (ARM64, 7.75 GiB Docker memory limit) with 2 `customer-web` replicas, 3 `risk-worker` replicas, 12 Locust users, a 4 users/second ramp, and a 30-second run.

| Measurement | Result |
|---|---:|
| Completed requests | 2,225 |
| Unexpected failures | 0 (0.00%) |
| Aggregate throughput | 74.49 requests/second |
| Aggregate median / p95 | 20 ms / 81 ms |
| Async ingestion | 1,514 requests at 50.69 requests/second |
| Async ingestion median / p95 | 13 ms / 52 ms |
| Sync predictions | 711 requests, 0 failures |
| Post-run Kafka lag | 0 on all 3 partitions |
| Persisted/scored transactions | 2,225 / 2,225 (100%) |
| Mean persisted detection latency | 55.72 ms |

The terminal summary includes requests completed during Locust's final partial reporting interval. `mfs_stats.csv` is a periodic machine-readable sample (2,161 requests at 74.44 requests/second); the complete terminal result and reconciliation are recorded in [`artifacts/loadtest/verification.md`](../artifacts/loadtest/verification.md). This is a reproducible local baseline, not a production capacity claim.

## Production path

For a real production deployment, place the stateless services under Kubernetes/ECS or an equivalent orchestrator, use managed highly available PostgreSQL/Redis/Kafka, configure Kafka TLS/SASL and topic partition/replication counts, store secrets in KMS/Vault, expose Prometheus/OpenTelemetry metrics, and define an SLO-driven autoscaling policy. Repeat this workload with production-like payload distributions and a formally approved target before making a capacity claim.
