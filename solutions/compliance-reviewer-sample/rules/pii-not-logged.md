# RULE-001: PII must not be logged in plaintext

## Standards
- SOC2 CC6.7 (Logical and Physical Access Controls — restricting unauthorized access)
- GDPR Article 32 (Security of processing — pseudonymisation and encryption)
- HIPAA §164.312(a)(2)(iv) (Encryption and decryption)

## Applies to
Any code that calls a logger function and includes user-identifying data:
- `Logger.info`, `Logger.debug`, `Logger.warn`, `Logger.error` (Elixir)
- `logger.info`, `logger.debug` (Python)
- `console.log`, `console.error` (JavaScript)
- `log.Info`, `log.Error` (Go)
- `rails logger`

## Detection
Look for log statements that interpolate variables matching PII patterns:
- email addresses (vars named `email`, `*_email`, `*.email`)
- phone numbers (vars named `phone`, `*_phone`, `mobile`)
- social security / tax IDs
- date of birth
- full name (`first_name + last_name`, `full_name`)
- physical addresses (street, city + zip)
- credit card numbers
- IP addresses (in some jurisdictions)

Flag if any of these are passed to a logger without a redaction wrapper.

## Severity
HIGH

## Suggested fix
Wrap PII fields with the project's `redact()` helper:
```
# Bad
logger.info("user signed in", email=user.email)

# Good
logger.info("user signed in", user_id=user.id, email=redact(user.email))
```

Or log only non-PII identifiers:
```
logger.info("user signed in", user_id=user.id)
```

## Exceptions
- Test files (`*_test.py`, `*_spec.rb`, `test/**`)
- Local development logs (gated behind `if (config.env == "dev")`)
- Already-hashed identifiers (`user.email_hash`)
