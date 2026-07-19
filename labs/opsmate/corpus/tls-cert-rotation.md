# TLS Certificate Rotation & Expiry

Fictional runbook for the OpsMate course. Company: Meridian Retail (fictional).

## Symptoms

- Clients fail to connect with `certificate has expired` or `x509: certificate has expired or is
  not yet valid`.
- The load balancer health check on `https://` flips to unhealthy while the `http://` check stays green.
- Synthetic monitors report a TLS handshake failure across every region at the same minute.

## Most likely cause

A certificate reached its **notAfter** date and was not rotated in time. The usual reason is that
the automated renewal job failed silently some days earlier and nobody watched the expiry gauge.

## Diagnosis

1. Read the live certificate's expiry:
   `echo | openssl s_client -connect edge.meridian.example:443 2>/dev/null | openssl x509 -noout -dates`.
2. Check the renewal job logs for the last successful run (`cert-manager` or the ACME cron).
3. Confirm the alert `tls_cert_expiry_days < 14` did or did not fire — if it did not, the exporter
   is scraping the wrong host.

## Resolution

- Trigger an immediate renewal: `kubectl -n cert-manager delete certificaterequest --all` forces
  cert-manager to re-issue, or run the ACME client manually for a non-Kubernetes edge.
- Once the new certificate is present, roll the terminating proxies so they pick it up.
- Verify the chain is complete — a missing intermediate produces the same client error as an expiry.

## Verification

- `openssl x509 -noout -dates` shows a notAfter at least 60 days out.
- The load balancer HTTPS health check returns to healthy.
- A fresh handshake from an external monitor succeeds.

## Prevention

Alert on `tls_cert_expiry_days < 21` per certificate, and treat a failed renewal job as a page, not
a warning. An expiry is always preventable — the failure is monitoring, not the certificate.
