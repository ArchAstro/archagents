# Daily Health Report Prompt

Cron-fires once per morning. Posts a prompt to the `health-reports`
thread, which triggers the agent (via the participate routine) to
generate today's report. The script reads the previous day's
continuity summary from `storage` (key `last_report_summary`) and
embeds it as starting context.


- Event: `schedule.cron`
- Handler: `script`
