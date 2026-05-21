# Compliance Review — PR #482: Add request logging to /api/users endpoint

**Reviewed by:** compliance-reviewer-agent
**Date:** 2026-04-07
**Findings:** 2

---

### CRITICAL — PII in log output (SOC2 CC6.7)

> `src/middleware/request-logger.ts`, line 34

```ts
logger.info('Incoming request', { path: req.path, body: req.body, headers: req.headers });
```

**Finding:** `req.body` is logged without field filtering. On this endpoint, the body contains `email`, `phone`, and `date_of_birth`. Logging unredacted PII to application logs violates **SOC2 CC6.7** (restrict information assets to authorized users/processes).

Logs ship to a shared Datadog index with 45-day retention and broad team access. This creates an uncontrolled copy of PII outside the primary datastore.

**Remediation:** Use the existing `sanitizeBody()` helper to strip sensitive fields, or switch to an allowlist pattern:

```ts
const safeBody = pick(req.body, ['action', 'resource_type', 'timestamp']);
logger.info('Incoming request', { path: req.path, body: safeBody });
```

---

### MEDIUM — No deletion mechanism for logged data (GDPR Art. 17)

> `infra/logging-config.yaml`, line 12

```yaml
retention_days: 90
deletion_policy: none
```

**Finding:** Logged request data has a 90-day retention with no automated deletion or anonymization pipeline. If the logged payloads contain personal data (they do — see finding above), this conflicts with **GDPR Article 17** (Right to Erasure). A data subject deletion request cannot be fulfilled for data already written to these logs.

**Remediation:** Either (a) ensure PII never reaches the logs (preferred — fixes both findings), or (b) configure log anonymization/purge triggers that the data-deletion pipeline can invoke.

---

*Auto-posted by compliance-reviewer-agent. Dismiss findings with `/compliance dismiss <id> <reason>`.*
