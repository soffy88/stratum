# KNOWN_BEHAVIOUR — reading_status and last_run_id

CLASS=known behaviour, not a bug
CHANGES_REQUIRED=none — recorded so it is not "fixed" by mistake
BASELINE=stratum-a-final

Two fields read as defects and are not. Both are properties of the chain's
history rather than of a projection, and changing either would mean changing
what the chain means.

## reading_status is always READING

```
reading_run.status   = 'READING'      the only value ever written
P7 reading_map.reading_status = 'READING'
```

The pipeline never advanced `reading_run.status` past `READING`. There is no
code path that writes a later state, and there is no table recording that a
chapter was finished, because nothing in the pipeline decided it was.

P7 reports the value it found and does not explain it. That is the correct
behaviour for a read-only projection: it arranges the rows A仓 wrote, and
`READING` is what A仓 wrote.

**Why not fix it.** Writing `COMPLETED` would mean inventing a completion rule
— page threshold? evidence count? — and no such rule exists or was asked for.
A guessed threshold in a field a reader treats as a fact is worse than a
constant.

## last_run_id is the last by id, not by time

```
last_run_id = max(id)          'arr_d0d1473d79fc'
```

`reading_run` has `started_at` and `completed_at` columns. P4.1's emitter does
not write them, so they are NULL in the database. Ordering by them is
therefore not merely discouraged but impossible — there is nothing to order by.

The result is deterministic, which is what P7's determinism gate needs: the
same id every time. It is not chronological, and a reader must not treat it as
a timeline.

**Why not fix it.** Populating the timestamps would be the real fix, and it
belongs upstream: the emitter in `persistence.py`, not the projection that
reads its output. It is listed in `A_FINAL_KNOWN_LIMITATIONS.md` §18 as part of
the staging-only durability item rather than here, because until then there is
nothing meaningful to record.
