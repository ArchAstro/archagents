# Example: Code Review Agent in action

A real example of what the Code Review Agent posts on a PR.

## The PR

Someone opens a PR adding a new function that handles user input.

```diff
+ def parse_user_input(raw):
+     data = json.loads(raw)
+     user_id = data["user_id"]
+     query = f"SELECT * FROM users WHERE id = {user_id}"
+     return db.execute(query)
```

## What the agent does

1. **Reads the diff** via `get_pr_files`
2. **Reads the surrounding code** via `get_repo_file` to confirm `db.execute`
   doesn't sanitize input
3. **Constructs a concrete failing scenario**: an attacker passes
   `user_id: "1; DROP TABLE users; --"` and the f-string injects it
4. **Posts ONE inline comment** anchored to the f-string line:

> **app/handlers.py:5** — SQL injection: f-string interpolation puts
> attacker-controlled input directly into the query. Use a parameterized
> query: `db.execute("SELECT * FROM users WHERE id = ?", (user_id,))`.

## What it doesn't do

- Doesn't comment "consider adding type hints" (style)
- Doesn't comment "missing docstring" (style)
- Doesn't comment "consider error handling" without a concrete scenario
- Doesn't post a body-only "overall this needs work" summary
- Doesn't post if there's nothing concrete to flag — silence is approval

## A reviewer's review of the agent

The agent's job is to act like a senior reviewer who actually reads the
code and only comments on things that would matter in a post-mortem.

Common patterns it catches well:
- SQL injection / command injection
- Auth checks missing on new endpoints
- N+1 queries in ORM code
- Race conditions in shared state
- Cross-org / multi-tenant data leaks
- Forgotten error handling on external API calls

Common patterns it correctly **ignores**:
- Code style (let your formatter handle that)
- Naming preferences (let your linter handle that)
- "Consider adding..." suggestions without a clear bug
- Refactoring suggestions for working code
