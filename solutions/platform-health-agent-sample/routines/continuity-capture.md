# Continuity Capture

Captures the trailing `<summary>...</summary>` block from agent
responses on monitored threads and writes it to `storage` (3-day TTL)
under a per-thread key. Tomorrow's prompter reads the matching key
as continuity context. Branches by `thread.key` so the daily report
and 5xx digest share one capture script.


- Event: `thread.message_added`
- Handler: `script`
