# Backup Restore Drill

Fictional runbook for the OpsMate course. Company: Meridian Retail (fictional).

## Purpose

How to restore the production database from a backup, and how to run the periodic restore drill that
proves the backups actually work. A backup you have never restored is a hope, not a backup.

## When you restore for real

- Accidental data loss (a bad migration, a wrong `DELETE`, a dropped table).
- Corruption that replication faithfully copied to every replica.
- A ransomware or destructive-actor event where you must return to a known-clean point in time.

## Restore procedure

1. Identify the target recovery point. For point-in-time recovery, pick the timestamp just before
   the damage: `SELECT max(ts) FROM audit_log WHERE ts < '<incident time>';` on a scratch restore.
2. Provision a fresh instance — never restore over the live primary until the restore is verified on
   the side.
3. Restore the base backup, then replay WAL to the target timestamp.
4. Validate the restored data on the scratch instance before any cutover: row counts, a few known
   records, referential integrity.

## Cutover

- Only after validation, stop writes to the damaged database, promote the verified restore, and
  repoint the application at it.
- Keep the damaged instance untouched for forensics; do not delete it.

## The restore drill (do this monthly)

- Restore the latest backup to a throwaway instance and run the validation checks. Record the
  restore duration — that number is your real recovery-time objective, not the one on a slide.
- If a drill fails, treat it as a SEV2: your disaster recovery is broken and you found out in a drill
  instead of an incident, which is exactly the point of the drill.

## Verification

- The restored instance passes the row-count and integrity checks.
- The measured restore time is within your recovery-time objective.
- The drill result is logged with the date and the duration.
