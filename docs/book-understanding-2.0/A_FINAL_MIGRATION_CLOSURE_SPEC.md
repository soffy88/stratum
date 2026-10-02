# A_FINAL_MIGRATION_CLOSURE_SPEC

SCOPE=A仓 migration closure: the smallest set of files that lets 070–082 apply
        and the chain run on a database with nothing in it
VERIFIED=2026-10-01 against `stratum_a_closure`, created empty and dropped first

## The claim being corrected

The closure was previously described as `070–082`. That is wrong, and wrong in
a way that looks like breakage rather than a missing prerequisite.

```
apply 070..082 to an empty database  ->  all 13 fail
  ERROR: schema "stratum" does not exist
  LINE 1: CREATE TABLE IF NOT EXISTS stratum.book_source (
```

No file in `src/stratum/db/pg_migrations/` contains `CREATE SCHEMA`. The
`stratum` schema comes from `src/stratum/db/pg_schema/`, which is a different
directory and a different mechanism from the migration chain.

Running the repository's own `stratum.db.run_pg_migrations upgrade` shows the
apparent size of the dependency: **54 migrations**, of which 13 are the A chain.
That is true of the tool, not of the dependency. 53 of those migrations belong to
BU2 and to work outside A仓, and the A chain does not need them.

## The real closure

Fifteen files, in this order:

```
src/stratum/db/pg_schema/001_stratum_base.sql     schema bootstrap
src/stratum/db/pg_schema/002_substrate_chunk.sql  schema bootstrap
src/stratum/db/pg_migrations/070_a_repository_foundation.sql
...
src/stratum/db/pg_migrations/082_a_paper_evidence_composite_fk.sql   (13 files)
```

### Verified

Applied to `stratum_a_closure`, created empty:

```
closure applied            0 failures
7 layer emitters applied   0 failures
22 A tables vs staging      0 differing
A tables present in schema 62   (40+ of them from pg_schema, not from the chain)
```

The 45 tables a freshly created database reports are **TimescaleDB internals**
(`_timescaledb_*`, `timescaledb_*`) that this container's `template1` carries.
They are extension catalog, not user data. Before the closure was applied the
database had no `stratum` schema at all.

### Neither missing relation, missing schema nor missing function

All 15 files applied under `ON_ERROR_STOP=1`, which aborts on the first error
rather than continuing. A migration that referenced a relation or function the
closure did not create would have failed there. It did not.

Note on exit codes, because they lied during this work: `psql -f` **without**
`-v ON_ERROR_STOP=1` prints errors and exits 0. Two checks in this effort passed
on that basis before being redone. Anything asserting "the migrations applied"
must set it.

## Known property: the closure is apply-once

Every file in the closure is re-appliable except 082.

```
070  re-applies cleanly        (CREATE TABLE IF NOT EXISTS)
075  re-applies cleanly
079  re-applies cleanly
080  re-applies cleanly
081  re-applies cleanly
082  FAILS
      ERROR: constraint "paper_evidence_same_catalog_source_fk"
             for relation "paper_evidence" already exists
```

082's `ADD CONSTRAINT` has no `DROP CONSTRAINT IF EXISTS` in front of it. It is
a frozen migration, so this is recorded rather than repaired: the fingerprint
stability check across the chain is one of the things this project is asserting,
and editing a migration to make a re-application convenient would trade a real
guarantee for a convenience nobody has asked for.

In practice `stratum.db.run_pg_migrations` records applied filenames in
`public._pg_migrations` and does not re-apply, so the normal path never hits it.
Applying the closure by hand twice does.

The alternative, if a future change wants idempotence here, is a new migration
`083` that drops and re-adds the constraint — additive, leaving 082 byte-unchanged.

## Reproduction

```sh
docker exec aii-postgres psql -U aii -d postgres \
  -c "DROP DATABASE IF EXISTS stratum_a_closure;" \
  -c "CREATE DATABASE stratum_a_closure;"

# apply the 15 files in the order above, each with
#   psql -v ON_ERROR_STOP=1 -q -1 -f <file>

# then the seven emitters, in migration order
python -m stratum.knowledge.a_repository.ku_evolution_runner      --sql …sql
python -m stratum.knowledge.a_repository.ku_identity_runner       --sql …sql
python -m stratum.knowledge.a_repository.condition_boundary_runner --sql …sql
python -m stratum.knowledge.a_repository.mechanism_runner         --sql …sql
python -m stratum.knowledge.a_repository.relation_runner         --sql …sql
python -m stratum.knowledge.a_repository.paper_runner            --sql …sql
python -m stratum.knowledge.a_repository.constraint_runner       --sql …sql
```

The ledger table is `public._pg_migrations`, **not** a table in the `stratum`
schema. Applying the chain by hand does not populate it; only the runner does.
