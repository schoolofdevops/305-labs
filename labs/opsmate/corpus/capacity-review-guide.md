# Quarterly Capacity Review Guide — Acme Platform Team

## Gathering the demand signals

A capacity review that starts from current utilisation graphs is already too late; start from
demand. Pull four signals for the trailing two quarters: peak requests per second per service
(the ninety-fifth percentile of daily peaks, not the single spike), storage growth per week for
every stateful system, the marketing calendar for launches and campaigns in the coming quarter,
and the product roadmap items that change traffic shape rather than volume — a new bulk-export
feature moves the profile toward long slow requests even if total volume is flat, and a new
mobile client typically doubles request count while halving average payload. Interview one
engineer from each product team for fifteen minutes; the roadmap document always lags what teams
actually intend to ship. Record every number with its source and date in the review sheet,
because next quarter's review begins by scoring how accurate this quarter's predictions were —
the error margin on your own past predictions is the only honest confidence interval you have
for the new ones. Signals older than ninety days get a staleness flag and a named owner to
refresh them before the review meeting, not during it.

## Modelling headroom and the growth curve

For each service compute effective headroom: the load at which the service breaches its latency
SLO, divided by current peak load. The breach point comes from load tests where they exist and
from the worst production incident where they do not — and a breach point taken from an incident
gets a wide uncertainty band around it. Model growth per service, never as one platform-wide
number: authentication grows with users, payments with transactions, search with catalogue size,
and internal batch systems with engineer count, which compounds faster than any of them.
Extrapolate each service's curve to the end of next quarter under three scenarios — expected,
high (expected plus the largest single marketing event on the calendar), and the contractual
worst case from enterprise commitments. A service whose high-scenario projection lands within
twenty percent of its breach point goes on the action list. Be suspicious of any service showing
flat growth for three quarters; more often than not its metric silently broke, and a flat line
from a broken gauge has walked more than one team straight into an outage that the review
existed to prevent.

## Cost, procurement and the action list

Every action item leaving the review carries four fields: the service, the specific risk with its
date ("payments projected within fifteen percent of breach by mid-November"), the chosen action
with its cost, and a named owner with a review date. Actions come in three costs, cheapest first:
configuration (raise a limit, tune a pool, fix a noisy neighbour), efficiency (cache, batch,
archive cold data — pays forever but takes engineering time), and capacity purchase (more
compute, bigger database tier — fastest and compounding in cost). Reserved-instance and committed-
use purchases need procurement lead time; anything the model says is needed within two quarters
gets initiated now, because the discount curve rewards commitment and the spot market punishes
panic buying during a capacity crunch. The review's output document is one page: the action list,
the three largest risks, and the accuracy score of last quarter's predictions. Circulate it to
engineering leadership within two days of the meeting while the context is warm, and file the
full working sheet beside it for the one engineer per quarter who wants to check the working.
