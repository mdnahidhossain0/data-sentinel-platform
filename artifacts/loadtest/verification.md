# Local scalability verification — 2026-10-07

This evidence was generated from the isolated **Scalability Verification Tenant** using synthetic transactions. It demonstrates the local topology and instrumentation; it is not a production capacity or fraud-loss claim.

## Test shape

- Docker Desktop, ARM64, 7.75 GiB Docker memory limit
- 2 Nginx-balanced `customer-web` containers (3 Gunicorn workers × 2 threads each)
- 3 `risk-worker` consumers across 3 Kafka partitions
- 12 Locust users, ramped at 4 users/second for 30 seconds
- 70% asynchronous Kafka ingestion, 20% synchronous low-risk prediction, 10% synchronous high-risk prediction

## Terminal result

| Endpoint | Requests | Failures | Median | p95 | Requests/s |
|---|---:|---:|---:|---:|---:|
| `POST /transactions/ingest` | 1,514 | 0 | 13 ms | 52 ms | 50.69 |
| `POST /risk/predict low` | 498 | 0 | 44 ms | 100 ms | 16.67 |
| `POST /risk/predict high` | 213 | 0 | 47 ms | 110 ms | 7.13 |
| **Aggregate** | **2,225** | **0** | **20 ms** | **81 ms** | **74.49** |

After the run, all three `mfs.transactions` partitions reported consumer lag `0`. Database reconciliation reported 2,225 transactions and 2,225 assessments (100% scoring coverage), with a measured mean ingestion-to-assessment latency of 55.72 ms. The KPI snapshot was persisted with `is_synthetic=true`.

The CSV files in this directory are written periodically by Locust and therefore omit the final partial interval: their aggregate row contains 2,161 requests, 0 failures, and 74.44 requests/second. `mfs_failures.csv` and `mfs_exceptions.csv` contain headers only, confirming no recorded failure or exception in the final run.

## Post-run resource snapshot

| Service | CPU | Memory |
|---|---:|---:|
| Customer web replica 1 | 1.06% | 381.4 MiB |
| Customer web replica 2 | 1.03% | 385.1 MiB |
| Risk worker (each, range) | 0.58–0.99% | 124.9–125.2 MiB |
| Kafka | 2.57% | 413.6 MiB |
| PostgreSQL (customer) | 0.45% | 82.88 MiB |
| Redis | 2.39% | 19.48 MiB |
| Nginx gateway | 0.04% | 9.53 MiB |

Resource values are a single post-run snapshot rather than peak utilization. Use time-series telemetry for production sizing.
