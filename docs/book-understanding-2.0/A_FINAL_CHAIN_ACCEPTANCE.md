# A仓 full-chain acceptance — P5 Evolution → P7

BASELINE=A_P5_EVOLUTION_FREEZE + A_P7_FREEZE
DATABASE=stratum_a_p3_fresh (scratch), compared against stratum_a_p3_staging
METHOD=apply from zero, replay, interrupt/resume, semantic row compare
STATUS=PASS (with two recorded caveats)

## What was built, and how

A scratch database `stratum_a_p3_fresh` was created in the same container,
bootstrapped, migrated and populated from nothing, then compared against the
staging database the two layer freezes were verified on.

```
CREATE DATABASE stratum_a_p3_fresh
  pg_schema/001_stratum_base.sql, 002_substrate_chunk.sql   (schema bootstrap)
  stratum.db.run_pg_migrations upgrade                        (54 migrations)
  7 layer emitters, applied in migration order
```

### The A chain is not self-sufficient

Applying 070–082 alone to an empty database fails immediately:

```
ERROR: schema "stratum" does not exist
LINE 1: CREATE TABLE IF NOT EXISTS stratum.book_source (
```

All 13 fail. The `stratum` schema comes from `src/stratum/db/pg_schema/`, which
is a separate bootstrap from `pg_migrations/`, and no migration in the
repository contains `CREATE SCHEMA`. Applying the chain by hand — which is what
was tried first — therefore produces thirteen identical failures, and a reader
who only tries that concludes the chain is broken.

Using the repository's own runner instead shows the real dependency: **54
migrations**, of which 13 are the A chain. The A chain sits on top of 53
earlier migrations and cannot be applied without them. Recorded because "apply
the A chain to a clean database" is not a procedure that works on its own, and
the failure mode looks like breakage rather than a missing prerequisite.

### Ledger

The applied-migration ledger is `public._pg_migrations`, not a table in the
`stratum` schema. Fresh: 54 rows, of which 13 match `^0[78][0-9]_a_`.
Staging: 13 rows, the same 13 A-chain names — which independently confirms the
ledger file the P5 Evolution `schema` gate was given.

## STEP 12 — semantic row equality with staging

### Schema

```
pg_dump --schema-only over all 22 A tables, fresh vs staging
IDENTICAL, 1679 lines
```

The only initial difference was pg_dump's `\restrict` nonce, a random
per-invocation security token and not schema. Full-schema dumps are **not**
comparable: fresh carries 62 tables in `stratum` and staging carries 22,
because staging never received migrations 047–049.

### Data

```
147 data rows each
22/22 tables match on row count
masking created_at: 0 rows only in fresh, 0 rows only in staging
```

Every id, content, locator, score, hash and status is identical. The **only**
difference is `created_at`, which records when a row was written — 23:37 on
the fresh run against 07:26 in staging, 157 timestamp fields in each.

This is **semantic row equality**, and it is deliberately not called
row-for-row. The two claims are different and only one of them is true here.

```
semantic row equality
  compared   id, content_hash, locator, payload, score, status, version,
             every hash and every foreign key
  excluded   created_at, and only created_at
```

`created_at` records when a row was written, so two databases built at different
times cannot agree on it; a fresh run at 23:37 and staging at 07:26 differ in
157 fields across 146 rows. Requiring them to match would mean freezing the
clock, and a normalised clock is a weaker guarantee than an honest exclusion:
it would let a future migration rewrite history undetected.

The exclusion is stated rather than buried, and it is narrow. A first attempt
compared positionally and reported 40 differing rows, which are the same rows
in a different physical order — the differing timestamp changed the sort.
Compared as multisets the two are equal.

What this does **not** claim: byte-identical dumps. `pg_dump` of the two
databases differs in 146 timestamp fields and in the physical row order of the
`reading_evidence` table, and nothing else.

## STEP 13 — replay x3 and interrupt/resume

All seven emitters, three consecutive applications:

```
run 1  cond=6 constraint=1 knowledge_unit=11 ku_conf=15 ku_freeze=12
       ku_idn=11 ku_rel=2 ku_rev=1 ku_revw=5 mech=1 node=3 paper=1
       paper_ev=4 relcand=1
       CONTENT=157097c6a69f7faee9b0a908dd9a80a2
run 2  identical, CONTENT=157097c6a69f7faee9b0a908dd9a80a2
run 3  identical, CONTENT=157097c6a69f7faee9b0a908dd9a80a2
```

The fingerprint covers ids, hashes, statuses and versions across the twelve
A tables the chain writes.

### Interrupt and resume

The database was dropped, rebuilt and migrated again, then only **three of
seven** emitters were applied:

```
interrupted state: cond=6 constraint=0 mech=0 node=0 paper=0 paper_ev=0 relcand=0
```

Genuinely partial — four emitters' work absent. Resume then re-ran **all
seven from the beginning** rather than only the remainder, which is the harder
case: every already-written row is re-offered to `ON CONFLICT DO NOTHING`.

```
after resume: CONTENT=157097c6a69f7faee9b0a908dd9a80a2
baseline:     CONTENT=157097c6a69f7faee9b0a908dd9a80a2
IDENTICAL
```

Resume converges on the uninterrupted state exactly.

### A comparison that could not see a difference

The first resume check reported a mismatch. It was wrong, not the data: the
captured value carried a `CONTENT=` prefix and was compared against a bare
digest, so the strings could never be equal. This is the second time in this
work a comparison produced a confident answer about nothing — the earlier one
compared two identical SQL error strings. The check was rewritten to strip the
prefix, and a negative control confirms it can still distinguish values.

## Caveat recorded against P7

The P7 acceptance check C5 counted tables matching `%projection%` OR `%p7%` and
asserted the result was 0. That is true on staging and **false** on a complete
database:

```
fresh (54 migrations)   translation_projection
                        translation_fragment_projection
                        visual_region_projection        -> 3
tables named *p7*       -> 0 on both
```

The three belong to migrations 047–049 and to other subsystems. C5 passed on
staging only because staging lacks them. The invariant P7 actually claims —
it declares no table of its own — holds on both databases and is better
measured by `*p7*` plus `schema_change_count()`. The broader pattern was a bad
proxy, and the fact that it passed for the wrong reason is worth more than the
zero it produced.
