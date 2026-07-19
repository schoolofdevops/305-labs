# VPN Access Loss

Fictional runbook for the OpsMate course. Company: Meridian Retail (fictional).

## Symptoms

- Engineers cannot reach internal tools (the bastion, the internal dashboards, the admin console).
- The VPN client connects but no internal route works, or the client fails to connect at all.
- Multiple people report it at once, across locations — an infrastructure signal, not one laptop.

## Most likely cause

Either the VPN gateway itself is unhealthy, or the identity provider the VPN authenticates against
is failing, or a firewall / route change severed the path to the internal network. A single-user
report is usually a client problem; a broad report is the gateway or the IdP.

## Diagnosis

1. Scope it: is it one person or many? Many people, many locations → gateway or IdP, not clients.
2. Check the VPN gateway health and capacity — is it up, and is it at its connection limit?
3. Check the identity provider (SSO): if login itself fails, the VPN is fine and the IdP is the
   fault. Confirm with a non-VPN SSO login.

## Resolution

- **Gateway down or saturated:** restart or scale the gateway; if at a connection cap, raise the
  limit or add a second gateway.
- **IdP failure:** this is usually outside your control — engage the IdP vendor and switch to the
  documented break-glass access path for responders who must get in now.
- **Route / firewall change:** if a recent network change severed the path, revert it; internal
  routes should reappear immediately.

## Verification

- A test engineer connects and reaches an internal-only endpoint.
- The gateway's active-connection count is healthy and below its limit.
- SSO login through the VPN succeeds.

## Break-glass

Keep a documented, audited break-glass path (a separate bastion with hardware-key auth) for when the
normal VPN or IdP is down. Access through it is logged and reviewed after every use.
