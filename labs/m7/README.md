# M7 lab assets — Ship the Model: KitOps, OCI Artifacts & Signing

This module is CLI-driven — the lab runs `kit`, `cosign`, `curl`, and `docker compose`
against artifacts M6 left on disk, so there is little bespoke code here. The runnable
pieces the lab depends on live under `labs/opsmate/` (the spine), not in this folder:

| Path | What it is |
| --- | --- |
| `labs/opsmate/compose.yaml` | Grows a **`registry`** service (Zot) beside model/app/ui — the last service the Compose spine adds. Arch-parameterised image (`ZOT_ARCH`), port `5100:5000`, `./data/zot` volume, `mem_limit: 256m`. |
| `labs/opsmate/registry/config.json` | Zot's config (the image ships none). Points storage at `/var/lib/registry` and disables TLS so the lab can use plain HTTP. |
| `labs/opsmate/Kitfile` | The ModelKit manifest for **`opsmate/model`** — packs the base GGUF (`model:`), the golden set (`datasets:`), and the prompts (`code:`), each its own layer. Relative paths only (absolute rejected). The lab edits the two model lines to also pack the M6 tuned GGUF as `1.0.0-candidate`. |
| `labs/opsmate/Kitfile.adapter` | Packs the 4.6 MB M6 LoRA adapter alone as **`opsmate/adapter:1.0.0`** — the "adapters travel light" artifact. Packed with `kit pack . -f Kitfile.adapter`. |
| `labs/opsmate/preflight.sh` | Gains an optional **`VERIFY_SIGNATURE=1`** branch: resolves `VERIFY_TAG` (default `1.0.0`) to a digest and `cosign verify`s it before the stack starts. Unset, skipped silently. The verify-before-deploy gate in miniature. |
| `labs/opsmate/Makefile` | `make up` now also seeds `./data/zot` and brings the registry along. New `make registry-catalog` prints the repos + tags. |
| `labs/opsmate/signing/` | Where `cosign generate-key-pair` writes `cosign.key` / `cosign.pub` (gitignored — the private key is your signet ring). |

## The pipeline the lab runs (all live)

```
labs/opsmate/            (the pack context — the opsmate dir IS the context)
   │  kit pack . -t localhost:5100/opsmate/model:1.0.0            (base GGUF)
   │  kit pack . -t localhost:5100/opsmate/model:1.0.0-candidate (M6 tuned, edited Kitfile)
   │  kit pack . -f Kitfile.adapter -t localhost:5100/opsmate/adapter:1.0.0
   ▼
Zot registry @ localhost:5100    (kit push --plain-http)
   │  opsmate/model:1.0.0            609.8 MiB   SIGNED ✓
   │  opsmate/model:1.0.0-candidate  609.8 MiB   unsigned (the gate blocks it)
   │  opsmate/adapter:1.0.0          4.3 MiB
   │  kit unpack --filter=code       (selective pull — prompts only, no 610 MB)
   ▼
cosign sign  (by DIGEST, v3 flags: --use-signing-config=false --tlog-upload=false)
cosign verify  (base PASSES; candidate FAILS — no signatures found)
   ▼
preflight VERIFY_SIGNATURE=1  (verify-before-deploy: base up, candidate refused)
```

## Persistence

`data/zot/` (the registry storage) and `signing/` (the keys) survive teardown — M8 pulls
the signed `opsmate/model:1.0.0` from this registry, so the artifacts must outlive the
Compose phase. `make down` removes containers, not the volume.

## Checks

- `checks.json` — the lab's success end-state: registry up, both model tags pushed, the
  adapter kit present, the base signature verifiable, the candidate unsigned. Heavy steps
  self-seed (bring the registry up, pack/push the kits from on-disk artifacts) so the
  check runs from a clean tree; assertions are shape-true, not digest-exact.
- `deep-dive.checks.json` — the Deep Dive page: manifest fetch shows the KitOps media
  types + layer sizes, the serving-image scan runs (severity-gated), the referrer/tree
  shows the signature attachment.
