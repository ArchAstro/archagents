# Slack Delivery

Forwards agent responses from monitored threads (health-reports,
health-alerts, 5xx-digest) to the configured Slack output channel.
Strips `<thought>`, `<thinking>`, and `<summary>` blocks; suppresses
`SKIP:`-prefixed responses; guards against tool-call leakage.


- Event: `thread.message_added`
- Handler: `script`
