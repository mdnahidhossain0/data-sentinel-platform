# Security and privacy controls

## Preserved controls

- Vendor-only Ed25519 private signing key; public verification and tamper detection remain intact.
- Vendor and customer projects retain isolated databases, cookies, authentication, CSRF, rate limiting, and audit histories.
- Vendor customer/API secrets remain hashed; Customer Portal license access stays customer scoped.
- Account state and license state remain separate and existing 82 baseline tests continue to pass.

## MFS controls

- Tenant organization is derived from the authenticated session/API key, never accepted from request JSON.
- Ingestion keys are random, shown once, and stored as a short lookup prefix plus SHA-256 digest.
- Connector passwords are Fernet encrypted with a required environment key and never rendered or logged.
- Transaction events exclude amount and PII; logging records identifiers/error types rather than payloads.
- Phone values are masked on ingestion; device fingerprints are represented as hashes; approximate coordinates reduce precision.
- Schema discovery uses fixed read-only metadata queries and flags likely PII fields.
- The LLM receives neither credentials nor raw SQL capability. Its selected tool must be allowlisted; ORM tools are read-only, bounded, tenant scoped, role checked, and audited.
- High-risk results create review cases; the model does not execute irreversible financial actions.
- Correlation IDs are accepted only as UUIDs or regenerated and returned in `X-Correlation-ID`.
- Retention deletion is explicit, configurable, dry-runnable, and audit-recorded.

## Production deployment requirements

The Compose stack is a local prototype boundary. Before production:

1. Terminate HTTPS at a trusted proxy, enable secure cookies/HSTS, and rotate all example credentials and Ed25519 keys.
2. Configure Kafka TLS/SASL, per-topic ACLs, a multi-broker replication factor, monitoring, and tested backup/recovery.
3. Move secrets to a managed secret store/KMS; protect model artifacts and database backups with encryption and access policies.
4. Use read-only database connector accounts restricted to approved schemas; restrict the Customer Portal network egress.
5. Add centralized immutable audit export, SIEM alerts, vulnerability scanning, dependency pin/lock, SAST/DAST, penetration testing, and incident-response procedures.
6. Validate retention/legal requirements, field-level permissions, data residency, model governance, and human-review policy with the deploying MFS operator.

No certification, regulatory approval, penetration-test result, or production fraud accuracy is claimed by this repository.
