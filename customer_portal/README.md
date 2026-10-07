# Sentinel Customer Portal

> The primary product is now **Data Sentinel AI — Secure MFS Transaction Intelligence & Risk Platform**. This file retains the legacy account/licensing guide; see the repository [root documentation](../README.md) for MFS architecture, Kafka, Airflow, ML, schema discovery, local LLM, security, and the end-to-end demo.

The public, customer-facing portal for Data Sentinel customers. **There is no self-registration.** A customer can only log in with an account that Vendor Portal staff created and provisioned. The Vendor Portal is the sole source of truth for customers, organizations, plans, licenses, license status/expiry, installations, API credentials and provisioning; this project is only the customer-facing window onto an already-provisioned customer.

This is an independent Django project. It never touches the Vendor Portal's database and never imports its models — all license data arrives over HTTPS from the Vendor's Cloud API.

## How a customer gets access

```
Vendor staff (Vendor Portal)
  -> Add Customer: name, email, temporary password, plan, start date/duration
  -> Vendor creates the Customer, the License, and the customer's Cloud API secret
  -> Vendor pushes the login to THIS portal:  POST /internal/provision/   (server-to-server)
  -> Vendor gives the customer their email + temporary password
Customer
  -> logs in here with those credentials (can change the password afterwards)
  -> dashboard / license / installations are fetched live:
       api_client -> GET {SENTINEL_CLOUD_URL}/api/v1/partner/status/
                     X-Sentinel-Account / X-Sentinel-Secret (this customer's own credentials)
```

What this project stores locally about a customer: a login (`CustomerUser`, username = email), an `Organization` holding the vendor's customer identifier (`external_id`) and that customer's Cloud API secret, and support tickets. **It does not store license, plan, price, expiry or installation data** — every page fetches it live.

The customer never sees or enters an Account ID or secret. There is no "Link Sentinel Account" step.

## Setup

```bash
python -m venv env && source env/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py runserver 8000
```

Required configuration (`.env`):

| Variable | Purpose |
|---|---|
| `SENTINEL_CLOUD_URL` | Base URL of the Vendor Portal's Cloud API (default `http://localhost:8001`) |
| `VENDOR_PROVISIONING_KEY` | Shared secret the Vendor Portal presents to `/internal/provision/`. Must equal the Vendor Portal's `VENDOR_PROVISIONING_KEY`. If empty, provisioning is refused entirely. |

Docker: `docker compose up --build`.

## Account status vs. license status

These are separate concepts controlled separately by the vendor:

- **Account status** (Vendor: Suspend / Reactivate / Archive customer) is pushed here and sets `CustomerUser.is_active`. A suspended or archived customer cannot log in, and an existing session stops working on its next request (Django's auth backend refuses to load an inactive user). The customer's password is untouched by status changes.
- **License status** (Vendor: revoke / suspend / extend / change plan / regenerate) is never pushed. It is read live from the Cloud API on every page, so the dashboard reflects the vendor's change immediately. A revoked license shows `REVOKED`; it does not lock the customer out of their account.

If a customer exists but has no license, they see: "No active license has been assigned to your account. Please contact your vendor."

## Security notes

- `/internal/provision/` is machine-to-machine only. It is authenticated solely by the shared `X-Vendor-Provisioning-Key` header (401 otherwise — verified, including for a logged-in customer session). Creating a *new* account requires email + password; a status-only update requires neither and never changes a password.
- The license key is **not in the page HTML at all** (not CSS-hidden). "Reveal"/"Copy" call `POST /license/reveal/`, which re-fetches the key server-side using the logged-in customer's own credentials and returns JSON. Verified live: the `/license/` response contains no `DSK1.`.
- Every customer-facing query is scoped to `request.user.organization`; support tickets from another organization return 404.
- Password reset works only on existing accounts (unknown emails get the same response and no email; nothing is ever created). Login is rate-limited per IP.
- Structured JSON logging, secure cookies/HSTS (`DJANGO_SECURE_COOKIES=True` behind HTTPS), WhiteNoise for static files, `/healthz/`.
- The Vendor's private Ed25519 signing key does not exist anywhere in this project.

## Tests

```bash
python manage.py test
```

31 tests: signup and link-account endpoints are 404; login success/failure; unauthenticated redirects; a suspended customer cannot log in and an active session is cut off; provisioning endpoint (wrong key, missing fields, create, status-only update); customer sees their vendor-created license; key absent from initial HTML; reveal works for the authenticated customer only; no-license and vendor-unavailable states; per-customer API credentials (A never queries with B's); organization isolation on tickets; password reset/change; `api_client` (success, 401, timeout, connection error).

## Verified end to end

The complete flow was run against the **real Vendor Portal and this portal, both running, over HTTP** (60 checks + 3 vendor-down checks, 0 failures; script: `scripts/e2e_live_check.py` in the Vendor Portal project): vendor creates Customer A and B → each gets a Yearly license and a provisioned login → signup/link pages 404 → A logs in and sees Yearly/ACTIVE → key masked and absent from HTML → reveal returns A's key only → A sees exactly A's 2 installations and not B's → B gets 404 on A's ticket → vendor revokes A's license (A sees REVOKED, B unaffected) and suspends B's (B sees SUSPENDED) → vendor suspends A's account (session cut off, fresh login rejected, B unaffected) → reactivation restores login with the same password → VIEWER role cannot create/revoke → audit trail recorded → with the Vendor Portal stopped, login still works and pages show a clean "couldn't reach the license server" state.

## Business Insights

A self-service analytics page (**Insights** in the nav) that connects directly to a database of order/payment data and computes statistics in plain Python — **no LLM, no external API call, nothing non-deterministic.** `insights/statistics_engine.py` is pure stdlib (`statistics` module): mean, median, population stdev, period-over-period percent change, and z-score anomaly detection (flags any day ≥2 standard deviations from the mean). `insights/views.generate_insights()` turns those numbers into plain-English bullet points via simple conditionals — e.g. *"Revenue is down 95.8% in the most recent 7 day(s) compared to the prior period"* — never a model call.

- **Load Demo Data** seeds a standalone SQLite file (`insights_demo.sqlite3`, zero setup) with ~90 days of realistic orders, including a deliberate dip in the last few days so there's something real to find.
- **Run Report** connects to that database (raw `sqlite3`/`psycopg2`, not Django's ORM — `insights/db.py`), computes the stats, and saves the result as an `InsightsReport` row (scoped to `request.user.organization`, same isolation guarantee as the rest of the portal — tested: org A gets a 404 on org B's report).
- Point it at a **real** database server instead by setting `INSIGHTS_DB_ENGINE=postgresql` + `INSIGHTS_DB_HOST`/`PORT`/`NAME`/`USER`/`PASSWORD` in `.env`. The only requirement is a table named `orders` with columns `id, created_at, amount, status` (`status` = `'success'`/`'failed'`) — adapt `insights/db.py`'s queries if a real deployment's schema differs.
- A database that's unreachable or times out is handled gracefully: the report is saved with `status=ERROR` and the page shows "Could not connect to the database" rather than crashing (tested with a mocked connection failure).

Verified live: seeded ~2,100 demo orders, ran a 90-day report, and confirmed both the numbers (93.4% success rate, $232,873.92 revenue, etc.) and the generated insight text correctly called out the seeded dip (a 95.8% revenue drop and a 9-point payment success decline in the most recent week, plus the specific anomalous dates) — see `insights/tests_statistics.py` (engine correctness, including the zero-baseline edge case) and `insights/tests_views.py` (seed → run → report, DB-unavailable handling, window-days clamping, organization isolation).

## Local development: cookie namespacing

This project sets `SESSION_COOKIE_NAME = "customer_sessionid"` and `CSRF_COOKIE_NAME = "customer_csrftoken"` (the Vendor Portal uses `vendor_sessionid` / `vendor_csrftoken`). This matters if you run both on the same host differing only by port (e.g. both on `localhost`): browsers scope cookies by domain only, not port, so without distinct names the two projects would otherwise share one cookie jar — an action on either app could invalidate the other's CSRF token mid-session, producing a `Forbidden (CSRF token from POST incorrect.)` 403 on login. See the Vendor Portal's `scripts/cookie_namespacing_check.py` for a live verification of this.

## Known limitations

- Provisioning is a best-effort push from the Vendor Portal. If this portal is down at that moment, the vendor sees the failure and uses **Retry Portal Sync** / **Reset Portal Password** once it's back.
- The temporary password is shown once to the vendor, who must relay it securely; nothing is emailed automatically.
- No caching of the last Cloud API response: if the vendor is unreachable the customer sees an error state rather than stale data.
- Login rate limiting uses Django's local-memory cache (per process); use a shared cache (Redis) with multiple workers.
