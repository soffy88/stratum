"""A Repository P6 — canonical KU identity.

P4 froze a unit under one id and P4.1 persisted it under another. All
eleven pairs differ, so anything that cited a P4 id does not match the
durable row it was cited for. P4.1 recorded this as an open item and said
it needed a decision, not a workaround.

This is the decision: **`knowledge_unit.id` is the canonical id.** It
already binds to the verification that admitted the unit, which is the
stronger provenance of the two, and it is already what P4.1 wrote and what
P5's revision chain links. The P4 freeze id becomes a registered alias that
resolves to it.

    citation ──> any id ever issued for a unit
                   │
                   ├─ already knowledge_unit.id ─────> canonical
                   │
                   └─ retired formula ──> ku_identity ──> canonical
                                                     │
                                                     └─ no row ──> UNRESOLVED

What this module deliberately does not do:

- **It does not mint a third id.** Canonicalization is about resolution,
  not renumbering. A new formula would be a third id per unit and would
  invalidate every persisted row and every revision link already written.
- **It does not rewrite `knowledge_unit.id`.** Nothing is renumbered;
  `KUIdentityViolation` is what any attempt to do so raises.
- **It does not add a `ku_canonical` table.** The canonical id is already
  the row's primary key. A second table asserting the same fact would be a
  third source of truth for one id — the disease this stage cures.

Rules:
- one id, one unit. `UNIQUE(alias_id)` is the database invariant behind it,
  and `ambiguous_ids()` is the application-side reading of the same rule.
- content-derived. Every id and fingerprint here is a sha256 of its inputs,
  so a rebuild produces the same rows and a replay writes nothing.
- unresolved is an answer. An id nothing claims comes back UNRESOLVED, not
  guessed at: the stage that issued it and the stage that failed to resolve
  it are both facts worth having.
- no B仓. Nothing here reads or names another repository, because an A仓
  identity that depended on one could not be checked.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Sequence, Tuple

from .evolution import (
    EVOLUTION_TABLES,
    ROW_BUCKETS,
    ROW_TYPES,
    EvolutionSink,
    EvolutionViolation,
    FreezeTransaction,
)
from .persistence import persisted_unit_id


IDENTITY_VERSION = "a-p6-v0.1"


class IdentityKind(str, Enum):
    """Which retired formula produced an alias.

    `FREEZE_LEGACY` is P4's `sha256(statement | evidence_fingerprint)`.
    There is no `DURABLE` member: the durable id is the canonical id, so it
    is not an alias and has no row here. Adding one would create a table
    entry whose alias equals its canonical, which `ku_identity_not_self`
    refuses anyway.
    """

    FREEZE_LEGACY = "FREEZE_LEGACY"


#: The exact vocabulary the migration's CHECK admits.
DECLARED_ALIAS_KINDS = frozenset(k.value for k in IdentityKind)


class IdentityPrecondition(Exception):
    """An alias may not be registered as given; nothing was written."""


class Resolution(str, Enum):
    """How an id was resolved. The three outcomes a caller may see."""

    CANONICAL = "CANONICAL"
    ALIAS = "ALIAS"
    UNRESOLVED = "UNRESOLVED"


@dataclass
class ResolutionResult:
    """What one lookup found."""

    requested_id: str
    canonical_ku_id: Optional[str]
    resolution: str

    @property
    def resolved(self) -> bool:
        return self.resolution != Resolution.UNRESOLVED.value


# ── identity formulas ────────────────────────────────────────────────────────

def canonical_ku_id(candidate_id: str, verification_id: str,
                    content_hash: str) -> str:
    """The one canonical id for a unit.

    Delegated to P4.1's own formula rather than restated here. Restating
    it would be a chance to drift from it, and drift in an id formula is
    exactly the failure this stage exists to end. P4.1's formula stays the
    definition; this name is what it is now called.
    """
    return persisted_unit_id(candidate_id, verification_id, content_hash)


def legacy_freeze_id(statement: str, evidence_fingerprint: str) -> str:
    """P4's retired id, recomputed rather than read.

    The alias table records the fingerprint, so a reader can rebuild the
    retired id from P4's own inputs and check the table against it. Reading
    the id out of a dict instead would only prove that P4 was internally
    consistent.
    """
    from .freeze import unit_id
    return unit_id(statement, evidence_fingerprint)


def encode_fingerprint(statement: str, evidence_fingerprint: str) -> str:
    """P4's hash input, encoded unambiguously.

    P4's retired formula is `sha256(statement | evidence_fingerprint)`. The
    two parts are stored as JSON rather than as that concatenation because
    the separator cannot be split out of a statement that happens to
    contain it, and a check that mis-parses its own input is not a check.

    Storing these at all is not duplication. `evidence_fingerprint` came
    from `verification.trace`, and P4.1's emitter never wrote that column to
    the database — so this row is the only durable record of the input that
    produced the retired id. Without it the alias could not be rebuilt, and
    the table would have to be taken on trust.
    """
    import json
    return json.dumps({"statement": statement,
                       "evidence_fingerprint": evidence_fingerprint},
                      ensure_ascii=False, sort_keys=True)


def decode_fingerprint(encoded: str) -> Tuple[str, str]:
    import json
    decoded = json.loads(encoded)
    return decoded["statement"], decoded["evidence_fingerprint"]


def identity_id(canonical: str, alias: str) -> str:
    """`kid_<sha256(canonical | alias)[:12]>` — content-derived."""
    digest = hashlib.sha256(f"{canonical}|{alias}".encode("utf-8")).hexdigest()
    return f"kid_{digest[:12]}"


def identity_hash(canonical: str, alias: str, alias_kind: str,
                  id_fingerprint: str) -> str:
    """`kidh_<sha256(...)[:16]>` — the replay fingerprint."""
    digest = hashlib.sha256(
        f"{canonical}|{alias}|{alias_kind}|{id_fingerprint}"
        f"|{IDENTITY_VERSION}".encode("utf-8")).hexdigest()
    return f"kidh_{digest[:16]}"


# ── rows ─────────────────────────────────────────────────────────────────────

@dataclass
class IdentityAlias:
    """One row of `ku_identity`: a retired id and the unit it answers to."""

    id: str
    canonical_ku_id: str
    alias_id: str
    alias_kind: str
    id_fingerprint: str
    identity_hash: str
    identity_version: str = IDENTITY_VERSION
    created_at: str = IDENTITY_VERSION


# ── transaction ──────────────────────────────────────────────────────────────

IDENTITY_TABLES = EVOLUTION_TABLES + ("ku_identity",)


class IdentitySink(EvolutionSink):
    """P5's transactional sink plus `ku_identity`.

    Identity rows live in the same transactional store as the units they
    name, so a registration cannot land without its unit and a unit cannot
    gain an alias in a transaction that then fails. Inheriting is also what
    keeps the staging discipline in one place: `fail_after` means the same
    thing here as it did in P4.1.
    """

    TABLES = IDENTITY_TABLES
    ROW_TYPES = {**ROW_TYPES, "ku_identity": IdentityAlias}
    ROW_BUCKETS = {**ROW_BUCKETS, "ku_identity": "identities"}

    def __init__(self, fail_after: Optional[int] = None):
        super().__init__(fail_after=fail_after)
        self.identities: Dict[str, IdentityAlias] = {}

    def reload(self) -> Dict[str, object]:
        reloaded = super().reload()
        reloaded["ku_identity"] = dict(self.identities)
        return reloaded


# ── the service ──────────────────────────────────────────────────────────────

class KUIdentityService:
    """Names the canonical id and resolves every retired one to it.

    Read-only with respect to knowledge_unit. It holds no write path to the
    table: registration appends to `ku_identity` and nothing else, which is
    what makes "no mutation of a frozen KU" structural rather than a promise.
    """

    def __init__(self, ingestion_pipeline, freeze_pipeline, durable_writer,
                 sink: IdentitySink):
        self.p = ingestion_pipeline
        self.store = ingestion_pipeline.store
        self.fp = freeze_pipeline
        self.writer = durable_writer
        self.sink = sink

    # ── the canonical id ────────────────────────────────────────────────────

    def canonical_of_unit(self, frozen_unit) -> str:
        """The canonical id of one frozen unit.

        Recomputed through P4.1's formula from the unit's own columns, so
        the answer is derived rather than looked up. An identity that could
        only be read out of a table would be a second source of truth.
        """
        return canonical_ku_id(frozen_unit.candidate_id,
                               frozen_unit.verification_id,
                               frozen_unit.content_hash)

    def canonical_id_of_unit_id(self, unit_id: str) -> Optional[str]:
        """The canonical id for any id this stage knows how to resolve."""
        return self.resolve(unit_id).canonical_ku_id

    def frozen_units(self) -> List:
        return [self.fp.store.frozen_units[k]
                for k in sorted(self.fp.store.frozen_units)]

    # ── registration ────────────────────────────────────────────────────────

    def register_frozen_unit(self, frozen_unit) -> IdentityAlias:
        """Register one unit's retired id, if it needs one.

        No row when P4's formula and P4.1's formula happen to agree: the
        canonical id is then already the only id, and recording the unit as
        its own alias would be a row asserting nothing.
        """
        canonical = self.canonical_of_unit(frozen_unit)
        legacy = frozen_unit.id
        if legacy == canonical:
            return None
        fingerprint = encode_fingerprint(frozen_unit.statement,
                                         frozen_unit.trace.get("fingerprint", ""))
        return self.register(canonical, legacy, IdentityKind.FREEZE_LEGACY,
                             fingerprint)

    def register(self, canonical: str, alias: str, alias_kind,
                 id_fingerprint: str) -> IdentityAlias:
        """Append one alias row. Idempotent on content."""
        kind = alias_kind.value if isinstance(alias_kind, Enum) else alias_kind
        ok, failed = self.check_registration_preconditions(
            canonical, alias, kind, id_fingerprint)
        if not ok:
            raise IdentityPrecondition(
                f"{alias} cannot be registered for {canonical}: "
                f"{', '.join(failed)}.")
        row = IdentityAlias(
            id=identity_id(canonical, alias),
            canonical_ku_id=canonical,
            alias_id=alias,
            alias_kind=kind,
            id_fingerprint=id_fingerprint,
            identity_hash=identity_hash(canonical, alias, kind, id_fingerprint))
        if row.id in self.sink.identities:
            return self.sink.identities[row.id]
        try:
            with FreezeTransaction(self.sink) as tx:
                tx.write("ku_identity", dict(row.__dict__))
        except Exception as error:
            raise IdentityPrecondition(
                f"identity row for {alias} was not written: {error}") from error
        return self.sink.identities[row.id]

    def check_registration_preconditions(self, canonical: str, alias: str,
                                        kind: str,
                                        id_fingerprint: str
                                        ) -> Tuple[bool, List[str]]:
        failed: List[str] = []
        if canonical == alias:
            failed.append("ALIAS_IS_CANONICAL")
        if kind not in DECLARED_ALIAS_KINDS:
            failed.append("UNKNOWN_ALIAS_KIND")
        if not (id_fingerprint or "").strip():
            failed.append("NO_ID_FINGERPRINT")
        unit = self.sink.units.get(canonical)
        if unit is None:
            # The alias table references knowledge_unit ON DELETE RESTRICT,
            # so a row for a unit that is not durable would fail at the
            # database. Caught here instead, where the reason can be said.
            failed.append("NO_SUCH_CANONICAL_UNIT")
        elif unit.freeze_status != "FROZEN":
            failed.append("CANONICAL_UNIT_NOT_FROZEN")
        existing = self.sink.identities.get(identity_id(canonical, alias))
        if existing is not None and existing.canonical_ku_id != canonical:
            failed.append("ALIAS_BOUND_ELSEWHERE")
        for row in self.sink.identities.values():
            if row.alias_id == alias and row.canonical_ku_id != canonical:
                failed.append("ALIAS_ALREADY_CLAIMED")
        # The shapes are identical, so a reader cannot tell them apart. An
        # alias must therefore never be another unit's canonical id.
        other = self.sink.units.get(alias)
        if other is not None and alias != canonical:
            failed.append("ALIAS_IS_ANOTHER_UNITS_CANONICAL")
        return not failed, failed

    # ── resolution ──────────────────────────────────────────────────────────

    def resolve(self, any_id: str) -> ResolutionResult:
        """Resolve any id ever issued for a unit to its canonical id.

        Canonical first, then alias. The order matters less than it looks —
        the uniqueness rules make the two namespaces disjoint — but
        resolving canonical first means an id that is already canonical
        costs one dictionary lookup and no scan.
        """
        if any_id in self.sink.units:
            return ResolutionResult(any_id, any_id, Resolution.CANONICAL.value)
        # The row id binds the canonical id too, and a caller holding only
        # an alias cannot compute it, so this is a scan rather than a
        # lookup. At a unit's own alias count that is nothing; at catalogue
        # scale it wants an index, which `idx_ku_identity_alias` provides
        # in the database.
        for existing in self.sink.identities.values():
            if existing.alias_id == any_id:
                return ResolutionResult(any_id, existing.canonical_ku_id,
                                        Resolution.ALIAS.value)
        return ResolutionResult(any_id, None, Resolution.UNRESOLVED.value)

    def resolve_all(self, ids: Sequence[str]) -> List[ResolutionResult]:
        return [self.resolve(value) for value in ids]

    def aliases_of(self, canonical: str) -> List[IdentityAlias]:
        return sorted((row for row in self.sink.identities.values()
                       if row.canonical_ku_id == canonical),
                      key=lambda row: row.alias_id)

    def canonical_of_alias(self, alias: str) -> Optional[str]:
        return self.resolve(alias).canonical_ku_id

    # ── no mutation ─────────────────────────────────────────────────────────

    def update_unit(self, unit_id_: str, **changes) -> None:
        raise EvolutionViolation(
            f"Knowledge unit {unit_id_} cannot be renumbered; an id is "
            "retired by registering an alias, never by rewriting the row.")

    def renumber(self, old_id: str, new_id: str) -> None:
        raise EvolutionViolation(
            "A knowledge unit is not renumbered. The canonical id is "
            "knowledge_unit.id and it is final; P6 resolves the retired ids "
            "instead of replacing them.")

    def repoint(self, alias: str, canonical: str) -> None:
        raise EvolutionViolation(
            "An alias is not repointed. UNIQUE(alias_id) means an id that "
            "resolves to one unit can never be made to resolve to another.")

    def update_identity(self, identity_id_: str, **changes) -> None:
        raise EvolutionViolation(
            "An identity row is immutable; a wrong row is corrected by "
            "resolving to the unit it already names.")

    def delete_identity(self, identity_id_: str) -> None:
        raise EvolutionViolation(
            "An identity row is immutable. Retiring an id means it resolves "
            "to nothing, which is a fact about the unit, not an edit here.")

    def delete_unit(self, unit_id_: str) -> None:
        raise EvolutionViolation("A knowledge unit cannot be deleted.")

    def depend_on(self, other_repository: str) -> None:
        raise EvolutionViolation(
            f"A仓 identity must not depend on {other_repository}; an identity "
            "that could not be checked on its own would not be an authority.")

    # ── queries ─────────────────────────────────────────────────────────────

    def identity_count(self) -> int:
        return len(self.sink.identities)

    def canonical_count(self) -> int:
        return len(self.sink.units)

    def orphan_identities(self) -> List[str]:
        return sorted(row.id for row in self.sink.identities.values()
                      if row.canonical_ku_id not in self.sink.units)

    def ambiguous_ids(self) -> List[str]:
        """Ids that claim more than one unit. GATE_1.

        Reads the same invariant `UNIQUE(alias_id)` enforces in the database,
        so a failure here means the application and the schema have diverged
        rather than that the data is merely odd.
        """
        seen: Dict[str, List[str]] = {}
        for unit_id in self.sink.units:
            seen.setdefault(unit_id, []).append(unit_id)
        for row in self.sink.identities.values():
            seen.setdefault(row.alias_id, []).append(row.canonical_ku_id)
        return sorted(alias for alias, targets in seen.items()
                      if len(set(targets)) > 1)

    def cross_namespace_collisions(self) -> List[str]:
        """Ids that are one unit's canonical id and another unit's alias.

        Both namespaces are `ku_<12 hex>`, so a reader cannot tell them
        apart from the id alone. An id in both sets is not ambiguous only
        by luck, and must never happen.
        """
        canonical = set(self.sink.units)
        return sorted(row.alias_id for row in self.sink.identities.values()
                      if row.alias_id in canonical)

    def unregistered_units(self) -> List[str]:
        """Durable units whose retired id nobody recorded.

        Not automatically a fault: a unit minted directly by a later stage
        may have no retired id at all. It is listed so the distinction
        between "no alias needed" and "alias forgotten" stays visible.
        """
        return sorted(unit_id for unit_id in self.sink.units
                      if not self.aliases_of(unit_id))

    def misbound_aliases(self) -> List[str]:
        """Aliases whose fingerprint does not rebuild the id it claims.

        The strongest available check that the table is right: recompute the
        retired id from the recorded fingerprint with P4's own formula and
        compare. A table that disagrees with itself is worse than no table.
        """
        wrong: List[str] = []
        for row in self.sink.identities.values():
            statement, fingerprint = decode_fingerprint(row.id_fingerprint)
            if legacy_freeze_id(statement, fingerprint) != row.alias_id:
                wrong.append(row.alias_id)
        return sorted(wrong)

    def duplicate_identities(self) -> List[str]:
        seen: Dict[str, int] = {}
        for row in self.sink.identities.values():
            seen[row.alias_id] = seen.get(row.alias_id, 0) + 1
        return sorted(alias for alias, count in seen.items() if count > 1)

    def resolution_report(self) -> Dict[str, object]:
        """Every id this stage knows about, and what each resolves to."""
        ids = sorted(set(self.sink.units)
                     | {row.alias_id for row in self.sink.identities.values()})
        outcomes: Dict[str, int] = {}
        for value in ids:
            resolution = self.resolve(value).resolution
            outcomes[resolution] = outcomes.get(resolution, 0) + 1
        return {
            "ids_seen": len(ids),
            "canonical_units": len(self.sink.units),
            "aliases": len(self.sink.identities),
            "by_resolution": dict(sorted(outcomes.items())),
            "ambiguous": self.ambiguous_ids(),
            "cross_namespace": self.cross_namespace_collisions(),
            "orphans": self.orphan_identities(),
            "misbound": self.misbound_aliases(),
        }


# ── SQL emission ─────────────────────────────────────────────────────────────

_IDENTITY_COLUMNS = ("id", "canonical_ku_id", "alias_id", "alias_kind",
                     "id_fingerprint", "identity_hash", "identity_version")


def _literal(value) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, Enum):
        value = value.value
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


def emit_identity_sql(store, verification_pipeline, freeze_pipeline,
                      sink) -> str:
    """The whole A chain plus `ku_identity` as ONE transaction.

    Reuses the P5 emitter's statement set and appends the identity rows
    after it, so a unit always exists before the row that names it. Every
    statement is ON CONFLICT DO NOTHING, which is what makes the file safe
    to run twice.
    """
    from .evolution import emit_evolution_sql

    inner = emit_evolution_sql(store, verification_pipeline, freeze_pipeline,
                               sink).splitlines()
    statements = [line for line in inner
                  if line.startswith("INSERT INTO")
                  and not line.startswith("INSERT INTO ku_identity")]

    for key in sorted(sink.identities):
        row = dict(sink.identities[key].__dict__)
        statements.append(
            f"INSERT INTO ku_identity ({','.join(_IDENTITY_COLUMNS)}) "
            f"VALUES ({','.join(_literal(row.get(c)) for c in _IDENTITY_COLUMNS)}) "
            f"ON CONFLICT (alias_id) DO NOTHING;")

    return "\n".join(["BEGIN;", "SET search_path TO stratum, public;"]
                     + statements + ["COMMIT;"]) + "\n"
