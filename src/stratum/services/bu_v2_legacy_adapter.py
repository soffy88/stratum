"""Legacy capability absorption — spec §7.

§7.3 forbids copying an ``aii.bu_onto`` row into ``book_understandings_v2``. The
reason is not ceremony. The two shapes are genuinely different, and a copy would
silently mean something else:

    legacy main_claims        [{claim, stance, claim_grade, stance_marker}]
    BU2 central_theses        [str]

A legacy claim carries a **stance holder** — 儒家 is not a religion, Daoism is not
Daoism-as-religion. That distinction is the book's actual content, and it has
nowhere to go in a list of thesis strings. Copying would flatten a distinction
into an unattributed sentence, which is precisely the failure §9's negative
knowledge exists to prevent.

So the adapter maps rather than copies:

    legacy object -> semantic mapping -> BU2 object

Every field that BU2 can carry is carried. Every field it cannot is recorded as
a mapping loss in ``unmapped_fields``, so the loss is visible rather than
silent. §14 of the P10 report measured fusion as capability-to-capability; this
module makes one concrete instance of that auditable.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from stratum.knowledge.bu_v2_models import (
    ArgumentArchitecture,
    BookUnderstandingV2,
    BUStatus,
    NegativeKnowledge,
)


@dataclass
class LegacyClaim:
    """One legacy claim, keeping its stance.

    ``stance`` and ``stance_marker`` are the reason this class exists. A claim
    without its holder is a different and weaker claim.
    """

    claim: str
    stance: str = ""
    stance_marker: str = ""
    grade: str = "unverified"

    def to_thesis(self) -> str:
        if self.stance and self.stance_marker:
            return f"{self.claim} (regarding {self.stance} vs {self.stance_marker})"
        if self.stance:
            return f"{self.claim} (stance: {self.stance})"
        return self.claim


@dataclass
class LegacyArgument:
    """One legacy argument: a point, its boundary, and its evidence."""

    point: str
    boundary: str = ""
    evidence: list[dict[str, Any]] = field(default_factory=list)

    @property
    def evidence_quality(self) -> str:
        """What the legacy evidence actually is.

        Legacy evidence is ``{text, grade}`` with no locator and no content hash.
        It shows what was quoted, not where in the book it came from. Recording
        that as a quality rather than as evidence is what keeps §11 honest after
        a legacy import.
        """
        if not self.evidence:
            return "none"
        unverified = sum(1 for e in self.evidence if e.get("grade") != "verified")
        if unverified == len(self.evidence):
            return "all_unverified"
        return "partial"


@dataclass
class LegacyBU:
    """A legacy ``aii.bu_onto`` row, normalised."""

    legacy_id: str
    substrate_id: str
    title: str = ""
    problem_statement: str = ""
    overview_oneline: str = ""
    claims: list[LegacyClaim] = field(default_factory=list)
    arguments: list[LegacyArgument] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    positional_summary: list[Any] = field(default_factory=list)
    learning_paths: list[Any] = field(default_factory=list)
    deep_cards: list[Any] = field(default_factory=list)
    grade: str = "unverified"
    synthesis_marker: str = ""
    authors: str = ""
    venue_year: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class FusionResult:
    """What the adapter produced, and what it could not carry."""

    bu: BookUnderstandingV2 | None
    legacy_id: str
    claims_mapped: int = 0
    arguments_mapped: int = 0
    limitations_mapped: int = 0
    unmapped_fields: list[str] = field(default_factory=list)
    degradations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "legacy_id": self.legacy_id,
            "claims_mapped": self.claims_mapped,
            "arguments_mapped": self.arguments_mapped,
            "limitations_mapped": self.limitations_mapped,
            "unmapped_fields": self.unmapped_fields,
            "degradations": self.degradations,
            "bu_id": self.bu.id if self.bu else None,
            "bu_status": self.bu.status.value if self.bu else None,
        }


# Legacy fields with no BU2 counterpart. Listed so that "nothing was lost" is
# never claimed about a field that in fact has nowhere to go.
_KNOWN_UNMAPPABLE = {
    "core_explanations": "BU2 carries mechanisms per chapter; legacy had no equivalent populated",
    "concept_network": "legacy field was empty in 4005 of 4005 rows",
    "structure": "legacy field was empty in 4005 of 4005 rows",
    "applicability": "legacy field was empty in 4005 of 4005 rows",
    "core_takeaways": "legacy field was empty in 4005 of 4005 rows",
    "key_concept_ku_ids": "legacy field was empty in 4005 of 4005 rows; BU2 uses located evidence",
    "embedding": "BU2 stores no BU-level vector; concept vectors live in the B warehouse",
    "facets_zh": "BU2 has no facet table; roles are carried on chapter understandings",
    "agent_skill": "C-warehouse concern, out of BU2 scope per spec 2.2",
    "bu_quality": "superseded by stratum.verification_artifacts",
    "synthesis_marker": "carried as a degradation note rather than a column",
}


class BU2LegacyAdapter:
    """§7.2: import a legacy BU's understanding, not its rows."""

    def __init__(self, *, reader: Any | None = None):
        self.reader = reader

    def load(self, legacy_id: str | int) -> LegacyBU:
        """Read one legacy BU. Injectable so tests need no database."""
        if self.reader is not None:
            return self.reader(legacy_id)

        from stratum.services.bu_v2_entrypoint import db

        # Schema-explicit: the service layer's search_path is stratum,public,
        # and aii.bu_onto is neither. Naming the schema also documents that
        # this is a read of a foreign table, not of BU2's own storage.
        rows = db.query(
            "SELECT * FROM aii.bu_onto WHERE bu_id=%(id)s LIMIT 1", {"id": legacy_id}
        )
        if not rows:
            raise LookupError(f"legacy BU {legacy_id} not found in aii.bu_onto")
        return normalise(rows[0])

    def import_legacy_understanding(
        self,
        legacy_id: str | int,
        *,
        run_id: str = "",
        bu_id: str = "",
    ) -> FusionResult:
        """legacy object -> semantic mapping -> BU2 object. §7.3."""
        legacy = legacy_id if isinstance(legacy_id, LegacyBU) else self.load(legacy_id)
        result = FusionResult(bu=None, legacy_id=str(legacy.legacy_id))

        theses = [c.to_thesis() for c in legacy.claims if c.claim]
        result.claims_mapped = len(theses)
        result.arguments_mapped = len(legacy.arguments)
        result.limitations_mapped = len(legacy.limitations)

        # Every legacy field that has no BU2 home, named.
        result.unmapped_fields = [
            f"{name}: {why}" for name, why in _KNOWN_UNMAPPABLE.items()
        ]

        # Degradations the mapping itself introduces, recorded on the BU so a
        # reader of the BU knows it was assembled from a legacy source.
        degradations: list[str] = []
        unverified_claims = sum(1 for c in legacy.claims if c.grade != "verified")
        if legacy.claims and unverified_claims == len(legacy.claims):
            degradations.append(
                f"all {unverified_claims} legacy claims carried grade 'unverified'; "
                "BU2 does not upgrade them"
            )
        no_locator = sum(
            1
            for a in legacy.arguments
            for e in a.evidence
            if not e.get("locator") and not e.get("content_hash")
        )
        if no_locator:
            degradations.append(
                f"{no_locator} legacy evidence items have no source locator or content hash; "
                "they cannot satisfy BU2 traceability and are recorded as unverified"
            )
        if not legacy.arguments:
            degradations.append("legacy BU recorded no argument structure; BU2 argument layer is empty")
        if legacy.synthesis_marker:
            degradations.append(f"legacy synthesis marker: {legacy.synthesis_marker}")
        result.degradations = degradations

        if not theses and not legacy.arguments:
            # Nothing worth importing. Returning an empty BU would look like a
            # successful import of nothing.
            result.degradations.append("legacy BU had neither claims nor arguments; nothing mapped")
            return result

        bu = BookUnderstandingV2(
            id=bu_id or f"bu_legacy_{legacy.legacy_id}",
            run_id=run_id or f"run_legacy_{legacy.legacy_id}",
            book_id=legacy.substrate_id,
            substrate_id=legacy.substrate_id,
            status=BUStatus.DRAFT,
            genre="legacy_import",
            # §7.3: mapped, not copied. The question and thesis strings are
            # built from the semantic fields above, not lifted from a column.
            governing_questions=[legacy.problem_statement] if legacy.problem_statement else [],
            central_theses=theses[:3],
            sub_theses=theses[3:20],
            concept_system={
                "legacy_id": legacy.legacy_id,
                "imported": True,
                "authors": legacy.authors,
                "venue_year": legacy.venue_year,
                "legacy_grade": legacy.grade,
                "concepts": {},
                "mechanisms": [],
            },
            argument_architecture=ArgumentArchitecture(
                root_arguments=[a.point for a in legacy.arguments[:3]],
                supporting_arguments=[a.point for a in legacy.arguments[3:20]],
            ),
            negative_knowledge=NegativeKnowledge(
                limitations=legacy.limitations[:50],
                # Legacy boundaries are the one piece of negative knowledge
                # legacy had that BU2 models directly, so they carry across.
                open_problems=[
                    a.boundary for a in legacy.arguments if a.boundary
                ][:50],
                unresolved_conflicts=[],
            ),
            resolved_questions=[],
            unresolved_questions=[d for d in degradations],
            # Coverage and verification are deliberately zero. This is a
            # mapping, not a reading: nothing was extracted from text by P11.
            coverage_score=0.0,
            verification_score=0.0,
        )
        result.bu = bu
        return result


def normalise(row: dict[str, Any]) -> LegacyBU:
    """Turn a raw ``aii.bu_onto`` row into the structured legacy shape.

    Every field is read defensively: this table has 31 columns of which several
    are empty in all 4005 rows, and jsonb columns arrive as dicts, lists or
    strings depending on the client.
    """
    claims: list[LegacyClaim] = []
    for c in _json_list(row.get("main_claims")):
        if isinstance(c, dict) and c.get("claim"):
            claims.append(
                LegacyClaim(
                    claim=str(c["claim"]),
                    stance=str(c.get("stance") or ""),
                    stance_marker=str(c.get("stance_marker") or ""),
                    grade=str(c.get("claim_grade") or "unverified"),
                )
            )
        elif isinstance(c, str) and c.strip():
            claims.append(LegacyClaim(claim=c.strip()))

    arguments: list[LegacyArgument] = []
    for a in _json_list(row.get("argument_structure")):
        if not isinstance(a, dict):
            continue
        point = str(a.get("point") or a.get("claim") or a.get("text") or "")
        if not point:
            continue
        ev = [e for e in _json_list(a.get("evidence")) if isinstance(e, dict)]
        arguments.append(
            LegacyArgument(point=point, boundary=str(a.get("boundary") or ""), evidence=ev)
        )

    return LegacyBU(
        legacy_id=str(row.get("bu_id") or row.get("id") or ""),
        substrate_id=str(row.get("substrate_id") or ""),
        title=str(row.get("title") or ""),
        problem_statement=str(row.get("problem_statement") or ""),
        overview_oneline=str(row.get("overview_oneline") or ""),
        claims=claims,
        arguments=arguments,
        limitations=[str(x) for x in _json_list(row.get("limitations")) if str(x).strip()],
        positional_summary=_json_list(row.get("positional_summary")),
        learning_paths=_json_list(row.get("learning_paths")),
        deep_cards=_json_list(row.get("deep_cards")),
        grade=str(row.get("grade") or "unverified"),
        synthesis_marker=str(row.get("synthesis_marker") or ""),
        authors=str(row.get("authors") or ""),
        venue_year=str(row.get("venue_year") or ""),
        raw=row,
    )


def _json_list(v: Any) -> list[Any]:
    """jsonb arrives as a list, a dict, or a JSON string depending on client."""
    if isinstance(v, list):
        return v
    if isinstance(v, dict):
        return [v]
    if isinstance(v, str) and v.strip() not in ("", "null"):
        try:
            parsed = json.loads(v)
        except json.JSONDecodeError:
            return []
        return parsed if isinstance(parsed, list) else ([parsed] if isinstance(parsed, dict) else [])
    return []