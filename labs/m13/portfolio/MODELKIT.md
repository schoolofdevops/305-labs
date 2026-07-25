# Signed ModelKit — reference by digest

> The model this platform serves, as a **signed, immutable artifact**. Reference it
> by **digest**, not by tag: a tag can be moved to point at different bytes; a digest
> *is* the bytes. This is the "what actually shipped" record.

## The kit

| Field | Value |
| --- | --- |
| Name | `opsmate/model` |
| Version | `1.2.0` |
| Digest | `sha256:____` (fill from your `kit push` output) |
| Registry | (your registry — in the lab, `localhost:5100`; in production, a real OCI registry) |
| Contents | the tuned GGUF, the golden eval set it was measured on, and the versioned prompts |

## Prove the signature

Anyone pulling this kit can verify it was signed by you and not tampered with:

```bash
cosign verify \
  --key cosign.pub \
  --allow-insecure-registry --insecure-ignore-tlog \
  <registry>/opsmate/model@sha256:____
```

A passing `cosign verify` is the whole point of signing: the artifact carries a
cryptographic claim of origin. Ship the `cosign.pub` (the *public* key) alongside this
file so a reviewer can run the check; never ship `cosign.key`.

## Why the golden set is inside the kit

The kit packs the eval set the model was measured on, so the artifact carries its own
yardstick. A reviewer can pull the kit, read `evals/golden.yaml`, and re-run the
measurement instead of trusting a number in a report. The eval report and the signed
artifact are two views of the same fact.
