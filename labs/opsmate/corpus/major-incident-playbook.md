# Major Incident Playbook — Acme Payments Platform

## Declaring a major incident

A major incident is declared when any of the following hold: customer-facing error rate above five
percent for more than five minutes; a full outage of the payments API in any region; a confirmed
data-integrity problem of any size; or a security event with possible customer impact. Any on-call
engineer may declare — you do not need permission, and a false alarm is always cheaper than a late
declaration. Declare by posting `INC MAJOR <one-line summary>` in the incident channel and paging
the incident-commander rotation. The person who declares does not automatically become the incident
commander; they hold the role only until the commander on rotation acknowledges, which the rota
targets within ten minutes. When in doubt about whether something qualifies, declare it — the
first duty of the playbook is to remove hesitation. Note down the time you first suspected impact,
because the timeline you write later starts there and customer-facing SLA credits are calculated
from suspected-impact time, not declaration time. If two incidents appear related, keep them under
one declaration until the commander explicitly splits them; split incidents drift apart and both
lose the shared context that usually holds the root cause.

## Roles and the first fifteen minutes

Three roles exist in every major incident and they must be three different people as soon as
headcount allows. The **incident commander** owns decisions and priorities; they do not touch
keyboards for diagnosis. The **operations lead** drives the actual investigation and remediation,
delegating hands-on tasks. The **communications lead** owns the status page, stakeholder updates,
and the running internal timeline — one update every fifteen minutes to the incident channel even
when the update is "no change", because silence reads as chaos. In the first fifteen minutes the
commander confirms the roles are filled, sets the first checkpoint time, and asks exactly three
questions: what is the customer impact right now, what changed most recently, and what is the
fastest safe way to reduce impact even partially. Impact reduction beats root-cause hunting in
this window. If a rollback of the most recent deploy is possible and low-risk, the default is to
roll back first and diagnose second. The operations lead names every action out loud in the
channel before taking it — "I am about to restart the payment workers in ap-south-1" — so the
timeline writes itself and no two engineers act on the same system at once.

## Communication templates and stakeholder cadence

External status-page updates use three fixed severities: investigating, identified, monitoring.
Never promise a resolution time on the status page; promise the time of the next update instead,
and always deliver that update even if nothing changed. The first external update should go out
within twenty minutes of declaration and must avoid internal jargon entirely: name the visible
symptom ("card payments may fail or take longer than usual"), not the suspected cause. Internal
stakeholder updates go to the leadership channel on a thirty-minute cadence and may include the
current hypothesis, clearly labelled as a hypothesis. The communications lead maintains a single
running document with a timestamped timeline of facts, decisions, and actions — facts and
hypotheses in separate columns, because during the postmortem the single most common failure is
discovering that a guess was written down as a fact and steered the response for an hour. When
the incident resolves, the final status-page update stays in monitoring state for at least one
business day before closing, and the communications lead owns scheduling the postmortem within
five business days while memories are fresh.

## Severity downgrade and closing criteria

An incident may be downgraded from major when all of the following hold for thirty continuous
minutes: customer-facing error rate back under one percent; no new related alerts firing; and the
remediation in place is understood — a mitigation whose mechanism nobody can explain does not
count, because mitigations that work for unknown reasons stop working for unknown reasons too.
Downgrade is the commander's call alone, announced in the channel with the specific evidence for
each criterion. Closing the incident entirely additionally requires: any temporary mitigations
(traffic drains, feature flags, scaled-up capacity) either made permanent or scheduled for
removal with a named owner and date; the timeline document frozen and linked; and the postmortem
scheduled with the three role-holders as required attendees. Do not let an incident close by
fading away — an explicit close message with the final impact numbers (duration, error volume,
affected customers if known) is what the finance team uses for SLA credits and what the next
on-call engineer searches for when something similar happens at a worse hour.
