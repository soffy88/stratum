"""A Repository P5.1 — mechanism chain.

    Frozen KU (P4/P4.1) ──> mechanism_node ──> mechanism_candidate

A mechanism here is a **candidate**: an ordered structure of evidence-linked
nodes, each sitting on a frozen knowledge unit of the same book. It records a
shape the book describes. It does not record why the shape matters, and it is
not a knowledge claim, an interpretation, an explanation, or an author
intention. Those belong to B仓, and a mechanism that tried to carry one would
be making a judgement A仓 has no authority to make.

Two disciplines, kept apart, because conflating them is the whole failure
mode this stage could have:

- **A chain is a structure.** Three roles in an explicit order, each node
  pointing at its own frozen unit. Checkable.
- **A chain is not a cause.** There is no `cause` column, no `effect`
  column, no `explanation` and no `proof`. The three fields are
  `trigger_event`, `transition_event` and `result_event` — the *names* are
  the discipline. See `MECHANISM_BANNED_FIELDS`.

The causal vocabulary a Chinese book actually uses — 因为, 导致, 所以, 造成 — is
**not** banned here. Those words are often the book's own, and P5.0's condition
guard already refuses them where a *precondition* is meant; a mechanism is an
event chain, and its natural register is causal. What is refused is a field
named `effect` carrying an interpretation. Compare `condition_constraint_
boundary_guard` in the P5.0 layer: same idea, opposite side.

Identity is derived in three non-circular steps, in this order. Getting the
order wrong is how P6 ended up with two ids for one object, so it is written
down rather than left to whoever writes the next stage:

    1. mechanism_id  = f(source_version_id, ordered unit ids, extractor_version)
    2. node_id       = f(mechanism_id, node_role, sequence_order, unit id)
    3. mechanism_hash = f(source_version_id, ordered node ids, extractor_version)

`mechanism_id` cannot depend on node ids, and node ids cannot depend on the
mechanism hash, or step 3 could never be computed. The node id includes the
node's evidence, so `mechanism_hash` covers evidence transitively — which is
what lets §9 of the review spec's replay contract and the §3.1 hash formula be
the same field rather than two overlapping ones.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Sequence, Tuple

from .identity import IdentitySink
from .persistence import FreezeTransaction


MECHANISM_VERSION = "a-p5-1-v0.1"

#: A real extraction. Never used by the pilot.
EXTRACTOR_VERSION = "mechanism_extractor_v1"

#: A chain declared to exercise the persistence contract. Not an extraction
#: result, and not evidence that the extractor works. A gate asserts the two
#: are distinguishable, so a pilot row can never be read as a finding.
PILOT_DECLARED_VERSION = "pilot-declared"

#: Column names a mechanism may not grow. These are the words that turn a
#: recorded structure into a recorded judgement.
MECHANISM_BANNED_FIELDS = ("cause", "effect", "explanation", "proof",
                            "reason", "why", "significance")

#: The three roles, in the order a chain runs.
ROLE_ORDER = ("TRIGGER", "TRANSITION", "RESULT")


class NodeRole(str, Enum):
    TRIGGER = "TRIGGER"
    TRANSITION = "TRANSITION"
    RESULT = "RESULT"


class MechanismStatus(str, Enum):
    """No VERIFIED, no CONFIRMED.

    `VERIFIED` is the success value of `ku_verification.verification_status`;
    a chain is not a verified proposition. `CONFIRMED` would be a second word
    for that same fact, which is how an object ends up with two identities.
    """

    GENERATED = "GENERATED"
    SUPPORTED = "SUPPORTED"
    REJECTED = "REJECTED"


#: A supported chain is final. A仓 corrects by appending a new chain under a
#: new hash, never by downgrading this one — the same rule that makes a frozen
#: unit and a superseded unit behave.
LEGAL_STATUS_TRANSITIONS: Dict[MechanismStatus, frozenset] = {
    MechanismStatus.GENERATED: frozenset({MechanismStatus.SUPPORTED,
                                          MechanismStatus.REJECTED}),
    MechanismStatus.SUPPORTED: frozenset(),
    MechanismStatus.REJECTED: frozenset(),
}


class MechanismViolation(Exception):
    """Raised on a forbidden mechanism-chain operation."""


class MechanismPrecondition(Exception):
    """A chain may not be written as given; nothing was written."""


# ── identity ─────────────────────────────────────────────────────────────────

def mechanism_id(source_version_id: str, unit_ids: Sequence[str],
                 extractor_version: str) -> str:
    """`mec_<sha256(...)[:12]>` — step 1 of the derivation order.

    No node ids and no evidence: this is the identity of the *extraction*,
    matching the P5.0 pattern where `id` excludes evidence and the hash
    includes it.
    """
    ordered = "|".join(unit_ids)
    digest = hashlib.sha256(
        f"{source_version_id}|{ordered}|{extractor_version}"
        .encode("utf-8")).hexdigest()
    return f"mec_{digest[:12]}"


def node_id(mechanism_id_: str, node_role: str, sequence_order: int,
            knowledge_unit_id: str, evidence_ids: Sequence[str]) -> str:
    """`men_<sha256(...)[:12]>` — step 2.

    Includes the node's evidence, so it is the node's content fingerprint and
    `mechanism_hash` covers evidence transitively.
    """
    evidence = "|".join(sorted(evidence_ids))
    digest = hashlib.sha256(
        f"{mechanism_id_}|{node_role}|{sequence_order}|{knowledge_unit_id}"
        f"|{evidence}".encode("utf-8")).hexdigest()
    return f"men_{digest[:12]}"


def mechanism_hash(source_version_id: str, node_ids: Sequence[str],
                   extractor_version: str) -> str:
    """`meh_<sha256(...)[:16]>` — step 3, the replay identity.

    The order of `node_ids` is the chain order, so re-ordering the same nodes
    produces a different chain and therefore a different hash. That is
    deliberate: the order is part of what was recorded.
    """
    ordered = "|".join(node_ids)
    digest = hashlib.sha256(
        f"{source_version_id}|{ordered}|{extractor_version}"
        .encode("utf-8")).hexdigest()
    return f"meh_{digest[:16]}"


# ── rows ─────────────────────────────────────────────────────────────────────

@dataclass
class MechanismNode:
    id: str
    mechanism_id: str
    knowledge_unit_id: str
    node_role: str
    sequence_order: int
    evidence_ids: List[str] = field(default_factory=list)
    created_at: str = MECHANISM_VERSION


@dataclass
class MechanismCandidate:
    id: str
    source_version_id: str
    mechanism_hash: str
    status: str = MechanismStatus.GENERATED.value
    extractor_version: str = EXTRACTOR_VERSION
    created_at: str = MECHANISM_VERSION
    nodes: List[MechanismNode] = field(default_factory=list)

    def roles(self) -> Dict[str, int]:
        counts = {role.value: 0 for role in NodeRole}
        for node in self.nodes:
            counts[node.node_role] += 1
        return counts


MECHANISM_COLUMNS = ("id", "source_version_id", "mechanism_hash", "status",
                     "extractor_version", "created_at")

NODE_COLUMNS = ("id", "mechanism_id", "knowledge_unit_id", "node_role",
                "sequence_order", "evidence_ids", "created_at")


# ── the chain ────────────────────────────────────────────────────────────────

class MechanismChainBuilder:
    """Composes a chain out of frozen units of one book.

    Takes a list of `(unit_id, node_role)` in explicit chain order. There is
    no sorting, no inference and no array position: the caller states the
    order, and the builder refuses anything that is not a well-formed chain.
    """

    def __init__(self, ingestion_pipeline, units: Optional[Dict] = None):
        """`units` is the durable unit table, keyed by `knowledge_unit.id`.

        Needed because a chain is given canonical unit ids while the
        candidate table is keyed by candidate id: a node names a frozen
        unit, and the evidence has to be reached through that unit's own
        candidate. Without the mapping the lookup silently returns nothing
        and every node looks un-evidenced.
        """
        self.store = ingestion_pipeline.store
        self.units = units if units is not None else {}

    def build(self, source_version_id: str, chain: Sequence[Tuple[str, str]],
              extractor_version: str) -> MechanismCandidate:
        """`[(unit_id, role), ...]` in chain order -> a candidate."""
        if not chain:
            raise MechanismPrecondition(
                "A mechanism needs at least one node; an empty chain is "
                "refused rather than written.")
        roles = [role for _, role in chain]
        for role in roles:
            if role not in {r.value for r in NodeRole}:
                raise MechanismPrecondition(f"unknown node role {role}")
        # Refused here rather than at write time. A chain missing a role can
        # never be supported, so building one and failing later would leave a
        # caller holding a candidate it can do nothing with.
        missing = [r.value for r in NodeRole if roles.count(r.value) < 1]
        if missing:
            raise MechanismPrecondition(
                f"chain is missing {', '.join(missing)}; a mechanism needs a "
                "trigger, a transition and a result.")

        unit_ids = [unit_id for unit_id, _ in chain]
        mid = mechanism_id(source_version_id, unit_ids, extractor_version)
        nodes: List[MechanismNode] = []
        for order, (unit_id, role) in enumerate(chain, start=1):
            evidence = self.evidence_of(unit_id)
            if not evidence:
                raise MechanismPrecondition(
                    f"node {unit_id} has no evidence; a mechanism node must be "
                    "evidence-linked.")
            nodes.append(MechanismNode(
                id=node_id(mid, role, order, unit_id, evidence),
                mechanism_id=mid,
                knowledge_unit_id=unit_id,
                node_role=role,
                sequence_order=order,
                evidence_ids=evidence,
            ))
        candidate = MechanismCandidate(
            id=mid,
            source_version_id=source_version_id,
            mechanism_hash=mechanism_hash(
                source_version_id, [n.id for n in nodes], extractor_version),
            extractor_version=extractor_version,
            nodes=nodes,
        )
        return candidate

    def candidate_of(self, unit_id: str):
        """The candidate behind a durable unit id, or None."""
        unit = self.units.get(unit_id)
        if unit is None:
            return None
        return self.store.ku_candidates.get(unit.candidate_id)

    def evidence_of(self, unit_id: str) -> List[str]:
        """Evidence a frozen unit is anchored to, via its own chain.

        unit -> candidate -> evidence, the same path A仓's other stages
        walk. An id that is not a durable unit resolves to nothing, which is
        how a chain naming an absent unit is refused.
        """
        candidate = self.candidate_of(unit_id)
        if candidate is None:
            return []
        return [candidate.evidence_id]


def chain_is_complete(candidate: MechanismCandidate) -> bool:
    """A chain is valid when each of the three roles appears at least once.

    Not expressible as a CHECK: a CHECK cannot count rows in another table,
    so a mechanism row with zero nodes, or with only a TRIGGER, is a state
    this database can hold. This function plus `completeness_gate` is the
    service gate that closes it. Recorded as KNOWN_LIMITATION 5.
    """
    roles = candidate.roles()
    return all(roles[role.value] >= 1 for role in NodeRole)


def transition(candidate: MechanismCandidate, target: MechanismStatus) -> None:
    """The only way a chain's status changes.

    SUPPORTED has no outgoing edge, so a supported chain is final and a
    correction is a new chain under a new hash.
    """
    current = MechanismStatus(candidate.status)
    if target not in LEGAL_STATUS_TRANSITIONS[current]:
        raise MechanismViolation(
            f"{current.value} -> {target.value} is not a legal mechanism "
            "transition; a supported chain is final and A仓 corrects by "
            "appending a new chain.")
    candidate.status = target.value


# ── durability ───────────────────────────────────────────────────────────────

MECHANISM_TABLES = ("mechanism_candidate", "mechanism_node")

_MECHANISM_ROW_TYPES: Dict[str, type] = {
    "mechanism_candidate": MechanismCandidate,
    "mechanism_node": MechanismNode,
}

_MECHANISM_BUCKETS: Dict[str, str] = {
    "mechanism_candidate": "mechanisms",
    "mechanism_node": "nodes",
}


class MechanismSink(IdentitySink):
    """Every sink up to P6, plus the two mechanism tables.

    Inherits so the staging discipline stays in one place, and so a node
    cannot land without its mechanism in the same store. One sink means one
    transaction can carry the whole chain, which is what the review spec's
    transaction contract needs.
    """

    TABLES = IdentitySink.TABLES + MECHANISM_TABLES
    ROW_TYPES = {**IdentitySink.ROW_TYPES, **_MECHANISM_ROW_TYPES}
    ROW_BUCKETS = {**IdentitySink.ROW_BUCKETS, **_MECHANISM_BUCKETS}

    def __init__(self, fail_after: Optional[int] = None):
        super().__init__(fail_after=fail_after)
        self.mechanisms: Dict[str, MechanismCandidate] = {}
        self.nodes: Dict[str, MechanismNode] = {}

    def commit(self, pending: Sequence[Tuple[str, Dict]]) -> None:
        staged: Dict[str, Dict[str, Dict]] = {
            table: {} for table in self.TABLES}
        for index, (table, row) in enumerate(pending):
            if self.fail_after is not None and index >= self.fail_after:
                self.rollbacks += 1
                raise RuntimeError(f"injected failure at write {index} ({table})")
            if table not in staged:
                raise MechanismViolation(f"unknown table {table}")
            staged[table][row["id"]] = row
        for table, rows in staged.items():
            row_type = self.ROW_TYPES[table]
            getattr(self, self.ROW_BUCKETS[table]).update(
                {key: row_type(**value) for key, value in rows.items()})
        self.commits += 1

    def reload(self) -> Dict[str, object]:
        reloaded = super().reload()
        reloaded["mechanism_candidate"] = dict(self.mechanisms)
        reloaded["mechanism_node"] = dict(self.nodes)
        return reloaded


class MechanismWriter:
    """Appends chains. Holds no path to anything upstream."""

    def __init__(self, ingestion_pipeline, sink: MechanismSink):
        self.store = ingestion_pipeline.store
        self.builder = MechanismChainBuilder(ingestion_pipeline)
        self.sink = sink

    def preconditions(self, candidate: MechanismCandidate
                      ) -> Tuple[bool, List[str]]:
        """Everything that must hold, checked before the transaction opens."""
        failed: List[str] = []
        if not candidate.nodes:
            failed.append("EMPTY_CHAIN")
        if candidate.source_version_id not in self.store.source_versions:
            failed.append("NO_SUCH_SOURCE_VERSION")
        if not chain_is_complete(candidate):
            failed.append("INCOMPLETE_CHAIN")
        orders = [node.sequence_order for node in candidate.nodes]
        if len(orders) != len(set(orders)):
            failed.append("DUPLICATE_SEQUENCE_ORDER")
        if orders != sorted(orders):
            failed.append("UNORDERED_CHAIN")
        for node in candidate.nodes:
            if not node.evidence_ids:
                failed.append("NO_EVIDENCE")
                continue
            if not self._node_chain_ok(node, candidate):
                failed.append("CROSS_SOURCE_VERSION")
                break
        for node in candidate.nodes:
            if node.mechanism_id != candidate.id:
                failed.append("NODE_MECHANISM_MISMATCH")
                break
        return not failed, failed

    def _node_chain_ok(self, node: MechanismNode,
                       candidate: MechanismCandidate) -> bool:
        """node -> knowledge_unit -> evidence -> the chain's own book.

        A cross-book or cross-version chain is refused: a mechanism is a
        structure within one source, and a chain that reaches into another
        book is not A仓 recording a mechanism.
        """
        unit = self.sink.units.get(node.knowledge_unit_id)
        if unit is None:
            return False
        if unit.source_version_id != candidate.source_version_id:
            return False
        for evidence_id in node.evidence_ids:
            evidence = self.store.evidence.get(evidence_id)
            if evidence is None or evidence.source_version_id != \
                    candidate.source_version_id:
                return False
        return True

    def write(self, candidate: MechanismCandidate) -> MechanismCandidate:
        """One chain and all its nodes, in one transaction.

        Order matters: the mechanism row goes first so the nodes' foreign
        key resolves, and both are in the same transaction so a failure
        leaves neither. There is no reachable state with a node and no
        mechanism, or a mechanism with half its nodes.

        Returns the **stored** object, not the one passed in. The sink holds
        a copy, so the caller's candidate is consumed and later lifecycle
        changes must go through what this returns — the same copy-on-write
        shape as P4.1's writer and P5.0's. Mutating the original would
        change an object the chain does not see, which is a quiet way to
        believe a transition happened when it did not.
        """
        ok, failed = self.preconditions(candidate)
        if not ok:
            raise MechanismPrecondition(
                f"{candidate.id} may not be written: {', '.join(failed)}.")
        if candidate.id in self.sink.mechanisms:
            # Replay. The same chain is a no-op, not a second copy.
            return self.sink.mechanisms[candidate.id]
        try:
            with FreezeTransaction(self.sink) as tx:
                tx.write("mechanism_candidate",
                         dict(candidate.__dict__, nodes=[]))
                for node in candidate.nodes:
                    tx.write("mechanism_node", dict(node.__dict__))
        except Exception as error:
            raise MechanismViolation(
                f"{candidate.id} was not written: {error}") from error
        return self.sink.mechanisms[candidate.id]

    # ── lifecycle ───────────────────────────────────────────────────────────

    def support(self, mechanism_id_: str) -> MechanismCandidate:
        """GENERATED -> SUPPORTED, only on a complete chain."""
        candidate = self.sink.mechanisms[mechanism_id_]
        if not chain_is_complete(self._with_nodes(candidate)):
            raise MechanismPrecondition(
                f"{mechanism_id_} is missing a role; a chain cannot be "
                "supported without a trigger, a transition and a result.")
        transition(candidate, MechanismStatus.SUPPORTED)
        return candidate

    def reject(self, mechanism_id_: str) -> MechanismCandidate:
        """GENERATED -> REJECTED. Not available from SUPPORTED."""
        candidate = self.sink.mechanisms[mechanism_id_]
        transition(candidate, MechanismStatus.REJECTED)
        return candidate

    def _with_nodes(self, candidate: MechanismCandidate) -> MechanismCandidate:
        if candidate.nodes:
            return candidate
        candidate.nodes = sorted(
            (n for n in self.sink.nodes.values()
             if n.mechanism_id == candidate.id),
            key=lambda n: n.sequence_order)
        return candidate

    # ── immutability ────────────────────────────────────────────────────────

    def update_mechanism(self, mechanism_id_: str, **changes) -> None:
        raise MechanismViolation(
            f"{mechanism_id_} cannot be updated; a correction is a new chain "
            "under a new hash, never an edit of this one.")

    def delete_mechanism(self, mechanism_id_: str) -> None:
        raise MechanismViolation(
            "A mechanism chain cannot be deleted. A chain that is no longer "
            "supported is REJECTED, which keeps the record and the reason.")

    def update_node(self, node_id_: str, **changes) -> None:
        raise MechanismViolation(
            f"{node_id_} cannot be updated; a changed chain is a new chain.")

    def merge_chains(self, *mechanism_ids: str) -> None:
        raise MechanismViolation(
            "A仓 has no authority to merge chains; deciding two structures "
            "are one is a semantic judgement.")

    def verify_chain(self, mechanism_id_: str) -> None:
        raise MechanismViolation(
            "A chain has no VERIFIED state; A仓 does not declare a recorded "
            "structure to be true.")

    def add_cause(self, *mechanism_ids: str) -> None:
        raise MechanismViolation(
            "A mechanism records a structure, not a cause. A causal claim "
            "belongs to B仓.")

    def update_verification(self, *args, **kwargs) -> None:
        raise MechanismViolation(
            "This layer never touches a verification.")

    # ── queries ─────────────────────────────────────────────────────────────

    def nodes_of(self, mechanism_id_: str) -> List[MechanismNode]:
        return sorted((n for n in self.sink.nodes.values()
                       if n.mechanism_id == mechanism_id_),
                      key=lambda n: n.sequence_order)

    def orphan_nodes(self) -> List[str]:
        return sorted(n.id for n in self.sink.nodes.values()
                      if n.mechanism_id not in self.sink.mechanisms)

    def orphan_mechanisms(self) -> List[str]:
        return sorted(m.id for m in self.sink.mechanisms.values()
                      if not self.nodes_of(m.id))

    def cross_source_nodes(self) -> List[str]:
        wrong: List[str] = []
        for node in self.sink.nodes.values():
            mechanism = self.sink.mechanisms.get(node.mechanism_id)
            unit = self.sink.units.get(node.knowledge_unit_id)
            if mechanism is None or unit is None:
                continue
            if unit.source_version_id != mechanism.source_version_id:
                wrong.append(node.id)
                continue
            for evidence_id in node.evidence_ids:
                evidence = self.store.evidence.get(evidence_id)
                if evidence is None or evidence.source_version_id != \
                        mechanism.source_version_id:
                    wrong.append(node.id)
                    break
        return sorted(set(wrong))

    def duplicate_orders(self) -> List[str]:
        seen: Dict[str, List[int]] = {}
        for node in self.sink.nodes.values():
            seen.setdefault(node.mechanism_id, []).append(node.sequence_order)
        return sorted(mid for mid, orders in seen.items()
                      if len(orders) != len(set(orders)))

    def missing_roles(self) -> List[str]:
        """Chains that could not be supported. Read by the completeness gate."""
        broken: List[str] = []
        for mid in self.sink.mechanisms:
            candidate = self._with_nodes(self.sink.mechanisms[mid])
            if not chain_is_complete(candidate):
                broken.append(mid)
        return sorted(broken)

    def duplicate_chains(self) -> List[str]:
        seen: Dict[str, int] = {}
        for mechanism in self.sink.mechanisms.values():
            seen[mechanism.mechanism_hash] = seen.get(
                mechanism.mechanism_hash, 0) + 1
        return sorted(h for h, count in seen.items() if count > 1)

    def pilot_rows(self) -> List[str]:
        return sorted(m.id for m in self.sink.mechanisms.values()
                      if m.extractor_version == PILOT_DECLARED_VERSION)

    def extracted_rows(self) -> List[str]:
        return sorted(m.id for m in self.sink.mechanisms.values()
                      if m.extractor_version != PILOT_DECLARED_VERSION)

    def traceability_percent(self) -> float:
        """mechanism -> node -> KU -> evidence, as a percentage."""
        total = 0
        traced = 0
        for mechanism in self.sink.mechanisms.values():
            for node in self.nodes_of(mechanism.id):
                total += 1
                unit = self.sink.units.get(node.knowledge_unit_id)
                if unit is None or not node.evidence_ids:
                    continue
                if all(self.store.evidence.get(e) is not None
                       and self.store.evidence[e].source_version_id
                       == mechanism.source_version_id
                       for e in node.evidence_ids):
                    traced += 1
        return round(100.0 * traced / total, 2) if total else 0.0


# ── SQL emission ─────────────────────────────────────────────────────────────

def _literal(value) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, Enum):
        value = value.value
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, (list, tuple)):
        return "ARRAY[" + ",".join(_literal(v) for v in value) + "]"
    return "'" + str(value).replace("'", "''") + "'"


def _values(row: Dict, columns: Sequence[str]) -> str:
    """One VALUES tuple.

    created_at is written as NOW() rather than passed in: a value supplied
    by the caller is a value that can disagree with the row already stored,
    and a replay must not try to rewrite a timestamp.
    """
    return ",".join("NOW()" if c == "created_at" else _literal(row.get(c))
                    for c in columns)


def emit_mechanism_sql(mechanisms, nodes) -> str:
    """Both tables as one transaction, mechanism before nodes.

    Every statement is ON CONFLICT DO NOTHING, so a replay writes nothing.
    """
    lines = ["BEGIN;", "SET search_path TO stratum, public;"]
    for key in sorted(mechanisms):
        row = dict(mechanisms[key].__dict__)
        row.pop("nodes", None)
        lines.append(
            f"INSERT INTO mechanism_candidate ({','.join(MECHANISM_COLUMNS)}) "
            f"VALUES ({_values(row, MECHANISM_COLUMNS)}) "
            f"ON CONFLICT (mechanism_hash) DO NOTHING;")
    for key in sorted(nodes):
        row = dict(nodes[key].__dict__)
        lines.append(
            f"INSERT INTO mechanism_node ({','.join(NODE_COLUMNS)}) "
            f"VALUES ({_values(row, NODE_COLUMNS)}) "
            f"ON CONFLICT (mechanism_id, sequence_order) DO NOTHING;")
    lines.append("COMMIT;")
    return "\n".join(lines) + "\n"


def banned_field_report() -> Dict[str, List[str]]:
    """Which banned field names appear anywhere in this stage.

    Structural: the row dataclasses, not a word scan of the source. A
    mechanism that grew an `effect` column would be a mechanism making a
    judgement, and this is where that is noticed.
    """
    rows = {}
    for name in MECHANISM_BANNED_FIELDS:
        found = []
        if hasattr(MechanismCandidate, name):
            found.append("mechanism_candidate")
        if hasattr(MechanismNode, name):
            found.append("mechanism_node")
        if name in MECHANISM_COLUMNS or name in NODE_COLUMNS:
            found.append("schema")
        rows[name] = found
    return rows


MECHANISM_NOTES = {
    "banned_fields": len(MECHANISM_BANNED_FIELDS),
    "roles": len(ROLE_ORDER),
    "legal_status_transitions": sum(
        len(v) for v in LEGAL_STATUS_TRANSITIONS.values()),
    "extractor_versions": (EXTRACTOR_VERSION, PILOT_DECLARED_VERSION),
}
