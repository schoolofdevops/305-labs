# On-Call Escalation Policy

Fictional runbook for the OpsMate course. Company: Meridian Retail (fictional).

## Purpose

Defines who to page, in what order, and how long to wait between escalations during a production
incident. Following it prevents both under-escalation (a lone responder stuck for an hour) and
over-escalation (waking a director for a self-healing blip).

## Severity levels

- **SEV1** — customer-facing outage or data loss. Checkout down, payments failing, data at risk.
- **SEV2** — major degradation, no full outage. Elevated errors, one region impaired, a key feature broken.
- **SEV3** — minor or internal-only impact. A dashboard is wrong, a non-critical job is late.

## Escalation ladder

1. **Primary on-call** acknowledges within 5 minutes. If no ack in 5 minutes, the page auto-escalates.
2. **Secondary on-call** is paged next. For a SEV1, page both primary and secondary immediately.
3. **Incident commander** is engaged for any SEV1, or any SEV2 that runs past 30 minutes.
4. **Engineering manager / director** is looped in on a SEV1 that runs past 60 minutes or has customer
   or press exposure.

## During the incident

- Open an incident channel and pin the timeline. One person owns comms, one owns the fix.
- Post a status update every 15 minutes on a SEV1, even if the update is "still investigating."
- Do not silently work the problem alone past the ack window — escalate rather than hero it.

## After the incident

- Declare resolution only after the leading indicator has held at baseline for 15 minutes.
- File a blameless post-incident review within 48 hours.
- Convert every manual step you took under pressure into a runbook or an automation.
