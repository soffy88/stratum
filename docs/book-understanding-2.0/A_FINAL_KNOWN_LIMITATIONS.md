# A_FINAL_KNOWN_LIMITATIONS

SCOPE=every limitation this project knows about and has not closed
BASELINE=stratum-a-final
STATUS=OPEN — none of these is fixed, and none is a defect introduced by the
       P5→P7 close-out

Collected here so a reader does not have to find them across five freeze
reports, two specs and an audit. Grouped by what would have to change to close
them, because that is the useful axis: four of these need a decision from a
person, and only two need code.

## A. Extractor limitations

The extractors are narrow, and their narrowness is not measured. Nothing below
is a bug — the system is correct about what it did extract.

1. **Condition recall is unmeasured.** P5.0 extracts conditions with a closed
   type vocabulary and reports 6 from one chapter of five sections. Nothing
   establishes how many conditions that chapter *should* yield. A recall figure
   would require a human annotation pass that has not been done.
   *To close:* an annotated gold set for one chapter, then recall against it.

2. **Mechanism extraction is untested for recall.** P5.1 yields 1 mechanism
   with 3 nodes and passes 13 gates, every one of which checks that what was
   produced is well-formed and traceable. None checks that a mechanism present
   in the text was found. Gate coverage and extraction quality are different
   things and only the first is measured.
   *To close:* same as above, per extractor.

3. **Boundary candidates are 0.** Not a failure — `ku_boundary_candidate` is
   empty because the pilot chapter yielded none, and the type vocabulary that
   would produce them is partly withheld. A reader seeing 0 cannot tell "none
   present" from "vocabulary does not cover what is present".
   *To close:* state which withheld types exist, and why they are withheld.

4. **Paper extraction covers one declaration shape.** P5.3 reports 1 candidate
   and 4 evidence rows. The cross-catalog hole 082 repairs was real and is
   closed; the breadth of what a "paper source" may be is still one shape.

5. **SOFT and SELF_DEFINED are 0.** Constraint quality categories that no
   pilot row earned. Reported as 0 rather than omitted, which is correct, but a
   reader should not read 0 as "no soft constraints exist in the literature".

## B. Database limitations

6. **The lifecycle state machine is service-enforced, not schema-enforced.**
   `ku_review_event.from_status` and `to_status` are each constrained to
   `{ACTIVE, QUARANTINED, SUPERSEDED}`, but **no constraint forbids an
   impossible transition** — `SUPERSEDED -> ACTIVE` satisfies both column
   checks. The transition rules live in `evolution.py`. A second writer that
   inserts directly would produce a state the service would never allow.
   *To close:* a trigger, or a table of legal transitions joined in a CHECK.

7. **Status is folded, not materialised.** `status_of()` scans a unit's review
   events per call. At 11 units irrelevant; at catalogue scale a reader wants a
   projection — and a projection is a cache, not authority, which is the whole
   argument P7 exists to make.
   *To close:* a materialised column with the fold as its only writer.

8. **`created_at` cannot be reproduced across databases.** Two databases built
   from the same commit differ in 146 timestamp fields. Acceptance therefore
   asserts *semantic* row equality, not row-for-row equality.
   *To close:* nothing should close this. A normalised clock would let a
   migration rewrite history undetected. See `A_FINAL_CHAIN_ACCEPTANCE.md`.

9. **Migration 082 is apply-once.** Its `ADD CONSTRAINT` has no preceding
   `DROP CONSTRAINT IF EXISTS`. `run_pg_migrations` does not re-apply, so the
   normal path is unaffected; applying the closure by hand twice fails.
   *To close:* a new `083`, leaving 082 byte-unchanged. See the closure spec.

## C. Authority limitations

10. **A仓 does not infer semantic judgement, and that is the design.** The
    frozen review ledger records what a reviewer said. It does not review the
    reviews. Judging whether a review is correct is a person's work.
    *To close:* not planned.

11. **Two ids per unit, still open.** The durable id follows P4.1 §5; P4's
    in-memory id still differs. P5's revision chain runs on the durable id.
    Unchanged since P4 and deliberately not worked around.
    *To close:* a decision, not a patch.

12. **P5 writes tables its own spec did not name.** A revision must persist a
    new unit, whose foreign keys reach `ku_candidate` and `ku_verification`, so
    the ancestry is written too. The same discovery P4.1 made. It widens P5's
    blast radius beyond what its spec claimed.
    *To close:* amend the spec, or narrow what a revision writes.

13. **P5.0–P5.5 read `_require_traceable` through a private name.** Gates are
    module functions, not methods, and calling a private method is a deliberate
    trade-off to avoid widening an already large module's surface.
    *To close:* promote it, or move the gates into the service.

## D. Coverage limitations

14. **One book, one chapter, five sections.** The entire corpus is chapter 1 of
    《利率史（第四版）》. Every count in every artifact — 11 units, 17 evidence,
    10 traversed — is a fact about that chapter and not about the system. The
    gates that pass are evidence that the pipeline is well-formed on this input.
    *To close:* a second book, which changes the corpus rather than the code.

15. **`reading_status` is permanently `READING`, and `last_run_id` is the last
    by id rather than by time.** Both are correct, both are recorded in full in
    `A_KNOWN_BEHAVIOUR_READING_STATUS.md`, and neither should be "fixed" by
    someone who reads a constant as an oversight.

16. **Traversal tiebreak carries no meaning.** Two units on the same page in the
    same section have no reading-order fact distinguishing them. They are ordered
    by `evidence_id`, which is stable and content-derived so replay agrees, and
    a reader must not read meaning into it.
    *To close:* not planned. The absence of the fact is the fact.

## E. Not yet verified

17. **`P5_0_CONDITION` was untracked until `2254f9a`.** Its implementation,
    contract test, artifact and freeze report are now committed and its 15
    gates are in the chain verdict. Earlier closure runs could not reproduce it
    from a clean checkout.
    *Status:* closed by the commit above.

18. **Durability is proven against staging only.** No production database has
    received a migration from 070 onward, and none is intended to until this
    list is worked through.
    *To close:* the remaining items, then a deliberate promotion.
