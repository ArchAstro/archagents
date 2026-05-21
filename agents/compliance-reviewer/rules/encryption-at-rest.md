# RULE-003: Sensitive fields must be encrypted at rest

## Standards
- SOC2 CC6.1 (Logical and Physical Access Controls — encryption)
- GDPR Article 32 (Security of processing)
- HIPAA §164.312(a)(2)(iv)
- PCI DSS Requirement 3.4

## Applies to
Schema definitions and migrations that introduce columns containing:
- Payment instrument data (card numbers, ACH routing/account)
- Authentication secrets (password hashes are OK; raw passwords are NOT)
- API keys, OAuth tokens, refresh tokens
- Personally identifying numbers (SSN, tax ID, passport)
- Health information (any field marked PHI)

## Detection
Look for:
- New migrations / schema changes that ADD columns
- Field names matching: `*_secret`, `*_token`, `*_key`, `password`,
  `card_number`, `card_cvv`, `routing_number`, `account_number`,
  `ssn`, `tax_id`, `passport`, `phi_*`, `medical_*`

Flag if the column type is plain `:string` / `VARCHAR` / `TEXT`
without an encryption wrapper.

## Severity
CRITICAL

## Suggested fix
Use the project's encrypted field type:

```elixir
# Bad
field :api_key, :string

# Good
field :api_key, EncryptedString
```

Or store only a hash:
```elixir
field :api_key_hash, :string  # the raw key never persists
```

For Postgres, consider `pgcrypto` extension or a Cloud KMS-backed
column-level encryption.

## Exceptions
- Test fixtures
- Public API tokens that are explicitly meant to be readable by clients
  (e.g., publishable Stripe keys `pk_*`)
