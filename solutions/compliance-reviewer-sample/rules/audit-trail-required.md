# RULE-002: Mutations to user records require an audit trail entry

## Standards
- SOC2 CC7.2 (System monitoring — change management)
- GDPR Article 30 (Records of processing activities)

## Applies to
Any code that creates, updates, or deletes records in tables/contexts
involving:
- `users`
- `accounts`
- `permissions`
- `roles`
- `subscriptions`
- `payments`
- Any table marked as PII or financial

## Detection
Look for INSERT / UPDATE / DELETE operations against the above tables:
- `Repo.insert`, `Repo.update`, `Repo.delete` (Ecto)
- `User.objects.create`, `.update()`, `.delete()` (Django)
- `prisma.user.create`, `prisma.user.update`, `prisma.user.delete`
- Raw SQL `INSERT INTO users`, `UPDATE users`, `DELETE FROM users`

Flag if the same function/handler does NOT also call an audit logging
function (`AuditLog.record`, `audit.log`, `record_audit_event`, etc.).

## Severity
HIGH

## Suggested fix
Wrap mutations in a transaction with an audit log write:
```
Repo.transaction(fn ->
  user = Repo.update!(changeset)
  AuditLog.record(:user_updated, actor: current_user, target: user, changes: changeset.changes)
  user
end)
```

## Exceptions
- Soft deletes (setting `deleted_at`) — these still require audit entries
- Test fixtures
- Background data migration tasks (must be logged at job level instead)
