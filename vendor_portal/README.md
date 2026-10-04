# Sentinel Vendor Portal

Private, internal control plane for the vendor of Data Sentinel. **It is the single source of truth** for customers, organizations, plans, licenses (status/expiry/assignment), installations, customer API credentials, and provisioning. It is never exposed to customers.

Separate Django project from the Customer Portal and from Data Sentinel itself; they communicate only over HTTP.

```
Vendor staff -> Vendor Portal -> Customer + License + Cloud API secret
                     |  POST {CUSTOMER_PORTAL_URL}/internal/provision/   (vendor -> portal, X-Vendor-Provisioning-Key)
                     v
              Customer Portal login   <-- customer logs in with credentials the vendor relays
                     |
                     |  GET /api/v1/partner/status/   (X-Sentinel-Account / X-Sentinel-Secret)
                     v
              Cloud API (this project, `cloudapi`)  -> that customer's license / plan / installations only

Data Sentinel install -> POST /api/v1/check-in/ -> Cloud API
```

## Creating a customer (the only way one exists)

**Customers → Add Customer** (SUPER_ADMIN / LICENSE_MANAGER only) captures company + contact info, the customer's login email, a temporary password (pre-filled with a random one), plan, start date and optional duration. One submit:

1. creates the `Customer` and its Cloud API secret (stored only as a hash);
2. generates the Ed25519-signed license for the chosen plan;
3. pushes the login to the Customer Portal (`email`, temporary password, customer identifier, API secret, status);
4. shows a result page: account ID, email, plan, license (masked), status, expiry, and the temporary password **once**, for you to relay securely.

The vendor never stores the temporary password. If the Customer Portal is unreachable, the customer and license are still created, a clear error is shown, and the audit log records the failure — use **Reset Portal Password** (issues a new temporary password and re-provisions) or **Retry Portal Sync** on the customer page.

Other customer actions: edit info (never touches credentials/license), **Suspend / Reactivate / Archive** (pushes account status to the Customer Portal; no password is sent), **Reset Portal Password**, **Portal API Credentials** (rotates the Cloud API secret and pushes it, so the two never drift).

**Account status vs. license status are separate.** Suspending/archiving a customer blocks their portal login; it does not change their license. Revoking/suspending a license does not lock the customer out of their account. License changes are never pushed — the Customer Portal reads them live from the Cloud API.

## Roles

`SUPER_ADMIN` (everything, manages staff), `LICENSE_MANAGER` (customers, licenses, plans, provisioning), `SUPPORT_AGENT` / `VIEWER` (read-only). Enforced by decorators on every mutating view; denied attempts are audit-logged (`permission_denied`). Verified over HTTP: a VIEWER cannot create a customer or revoke a license.

## License cryptography

`DSK1.<payload>.<signature>`, Ed25519. The **private signing key exists only in this project's environment** (`LICENSE_SIGNING_PRIVATE_KEY_B64`) — never in the database, API responses, logs, or the Customer Portal; provisioning payloads contain neither it nor the license key (tested). The public verification key is hardcoded in `licenses/crypto.py` and matches Data Sentinel's `licensing/crypto.py`, so licenses issued here activate there. Services: `generate_license`, `revoke_license`, `extend_license`, `change_plan`, `regenerate_license` (`licenses/services.py`) and `verify_license_key` (`licenses/crypto.py`).

`.env.example` ships a **development** private key matching the hardcoded public key so the projects work together out of the box. Rotate before production (`python manage.py generate_signing_key`; update `VENDOR_PUBLIC_KEY_B64` here and in Data Sentinel, redeploy both).

## Cloud API

- `POST /api/v1/check-in/` — Data Sentinel installs. Accepts only `{license_key, installation_id, agent_version, plan}`; never orders, payments, `SystemEvent`s, logs or monitoring data. Rate-limited.
- `GET /api/v1/partner/status/` — Customer Portal. Authenticated by `X-Sentinel-Account` + `X-Sentinel-Secret` (the secret is provisioned automatically; the customer never sees it). Returns only that customer's data — Customer A's ID with Customer B's secret is a 401 (tested). If a customer's only license is revoked, the revoked license is returned so the customer sees `REVOKED`.

## Setup

```bash
python -m venv env && source env/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py seed_demo_data        # Monthly $29 / Yearly $249 plans (+ a demo customer)
python manage.py createsuperuser       # then set its role to SUPER_ADMIN in /admin/, or create staff via Admin Users
python manage.py runserver 8001
```

Key settings: `LICENSE_SIGNING_PRIVATE_KEY_B64`, `CUSTOMER_PORTAL_URL` (where the Customer Portal runs), `VENDOR_PROVISIONING_KEY` (must equal the Customer Portal's). Docker: `docker compose up --build`. Ops: `/healthz/`, `python manage.py expire_licenses` (cron), CSV export on the license list, WhiteNoise static files, HSTS/secure cookies when `DJANGO_SECURE_COOKIES=True`, structured JSON logging.

## Audit

Logged: login, logout, failed login, customer created/updated/suspended/reactivated/archived, license generated/revoked/suspended/reactivated/extended/plan-changed/regenerated, portal provisioned / provision failed / status synced / password reset / secret rotated, `partner_api_access`, `partner_api_auth_failed`, `cloud_check_in`, `permission_denied`.

## Tests

```bash
python manage.py test        # 30 tests
```

Covers: customer + license creation with the provisioning payload; secrets/passwords not stored in plaintext; portal-unreachable path; duplicate email; status pushes (no password/secret sent); account-vs-license independence; password reset pushes new password + secret; read-only roles blocked from creating customers and modifying customers/licenses; anonymous blocked; partner API identity mapping, cross-customer isolation, wrong-secret rejection, installation scoping, live license status; Ed25519 generate/verify/tamper/expiry/revoke/extend; check-in API; staff login/logout/failed-login auditing; password change; super-admin-only staff management.

## Live end-to-end check (real servers, no mocks)

`scripts/e2e_live_check.py` drives the full acceptance flow over HTTP against both running projects:

```bash
# terminal 1 (Vendor Portal)   CUSTOMER_PORTAL_URL=http://localhost:8000 VENDOR_PROVISIONING_KEY=live-shared-key \
#                              python manage.py runserver 8001 --noreload
# terminal 2 (Customer Portal) SENTINEL_CLOUD_URL=http://localhost:8001 VENDOR_PROVISIONING_KEY=live-shared-key \
#                              python manage.py runserver 8000 --noreload
# (Vendor needs staff users manager=LICENSE_MANAGER and viewer=VIEWER, password staff-pass-12345, plus seed_demo_data)
python scripts/e2e_live_check.py
```

Last run: 60 checks + 3 vendor-down checks, 0 failures — including vendor creates customers A and B, no signup on the Customer Portal, login, Yearly/ACTIVE dashboard, masked key absent from HTML, server-side reveal, installation and ticket isolation, license revoke/suspend reflected live, account suspension cutting off an active session and blocking fresh login, reactivation, VIEWER denied, audit entries, and graceful degradation with the Vendor Portal stopped.

## Local development: cookie namespacing

If you run this alongside the Customer Portal on the same host and differing only by port (e.g. both on `localhost`), be aware that browsers scope cookies by **domain only, not port** (RFC 6265) — without namespacing, both projects' default `sessionid`/`csrftoken` cookies would collide in one cookie jar. An action on one app (e.g. logging in, which rotates the CSRF cookie) could then invalidate a login form already open on the other, producing a confusing `Forbidden (CSRF token from POST incorrect.)` 403 on submit.

This project sets `SESSION_COOKIE_NAME = "vendor_sessionid"` and `CSRF_COOKIE_NAME = "vendor_csrftoken"`; the Customer Portal sets `customer_sessionid` / `customer_csrftoken`. Verified with `scripts/cookie_namespacing_check.py` (run both servers, then run the script) — confirms both cookies coexist with no overlap and that activity on one project never disturbs the other's token.

## Known limitations

- Provisioning is a best-effort push with manual retry (no background queue). Temporary passwords are relayed by the vendor; nothing is emailed automatically.
- The shared `VENDOR_PROVISIONING_KEY` is a single symmetric secret between the two vendor-owned systems; rotate it in both `.env` files together.
- Rate limiting is per-process (local-memory cache); use Redis with multiple workers. 2FA is a field only (`two_factor_enabled`), not a flow. No Celery/Redis infrastructure.
