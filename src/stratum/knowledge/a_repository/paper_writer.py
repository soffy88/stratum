"""A Repository P5.3 — paper / source metadata annotation.

    book_source (catalog) ──> source_version ──> paper_source_candidate
                                       └──────> paper_evidence

A source annotation here is a **candidate**: what a record declares about a
source, plus the record that made each declaration.

The distinction the whole stage turns on:

- **A declaration is a fact about a record.** "The catalog row states the author
  is X" is checkable: read the row, compare the string. That is what
  `declaration_matches_catalog` does.
- **A declaration is not a judgement about the source.** Nothing here says an
  author is authoritative, a publisher is reputable, or a book is important.
  Those are the words `PAPER_BANNED_FIELDS` refuses.

The evidence for each declaration is the **catalog row**, not a span of the
book's text, and that is a measured decision rather than a preference. The
frozen corpus is 17 spans totalling 671 characters of chapter-1 body text, and
across all of it the author surnames, the publisher, the ISBN and any
publication year occur **zero** times. There is no span that declares who wrote
the book, so attaching one would have made traceability a fabrication. Instead
`paper_evidence.catalog_source_id` is a foreign key to the record, and every
`declared_value` is compared against the field it claims to come from.

The limitation this leaves is recorded rather than papered over: *declaration by
text span is untested*. `declared_in` keeps room for TITLE_PAGE and
COPYRIGHT_PAGE so that ingesting front matter later has somewhere to record
provenance; neither is exercised now.

Identity is derived in two steps:

    1. paper_id     = f(source_version_id, book_source_id, source_type,
                        extractor_version)
    2. paper_hash   = f(1's inputs, title, authors, publication_year,
                        publisher, doi, isbn)

`paper_hash` covers every declared field including `publisher` — the review
spec's §5 formula listed doi and isbn but not publisher, which would have let a
publisher change slip through without changing the fingerprint. It deliberately
does **not** cover evidence: new evidence for the same source is new *evidence*,
not a new *source*, and `paper_evidence.evidence_hash` is that layer's own
replay key.

`authors` is **not** sorted before hashing. Author order carries meaning — first
author, corresponding author — so normalising it away would destroy a fact. The
pilot stores the catalog's author field verbatim as a single element, because
splitting "[美]悉尼·霍默 理查德·西勒" into two names is author identity
resolution, which LIMITATION-2 puts out of scope.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Sequence, Tuple

from .identity import IdentitySink
from .persistence import FreezeTransaction


PAPER_VERSION = "a-p5-3-v0.1"

#: A real extraction. Never used by the pilot.
EXTRACTOR_VERSION = "paper_extractor_v1"

#: A candidate declared to exercise the persistence contract. Not an extraction
#: result, and not evidence that the extractor works. It is inside paper_hash,
#: so an extractor run over the same catalog row produces a different candidate
#: rather than being swallowed as a replay.
PILOT_DECLARED_VERSION = "pilot-declared"

#: What kind of source this is. UNKNOWN is absent by design: an unreadable
#: source is a read state, not a fact, and a column that could hold it would let
#: "we could not tell" be stored as "it is a book".
SOURCE_TYPES = ("BOOK", "PAPER", "ARTICLE", "REPORT", "ARCHIVE")

#: The word the review spec banned as a fact. Recorded so the refusal is
#: testable rather than an absence.
FORBIDDEN_SOURCE_TYPE = "UNKNOWN_AS_FACT"

#: What kind of declaration a paper_evidence row records.
STATEMENT_TYPES = ("AUTHOR", "TITLE", "PUBLICATION", "YEAR", "IDENTIFIER")

#: Which kind of record made a declaration. Only the catalog row exists in this
#: corpus; the other three are where front matter would be recorded if it were
#: ever ingested, and none of them is exercised now.
DECLARED_IN = ("BOOK_SOURCE_CATALOG", "TITLE_PAGE", "COPYRIGHT_PAGE",
               "CIP_RECORD")

#: The only declaration source this corpus can supply.
CATALOG_DECLARATION = "BOOK_SOURCE_CATALOG"

#: statement_type -> the catalog field a declaration of that type must equal.
#:
#: This mapping is the traceability gate expressed as data. A declaration whose
#: value does not match the field it names cannot be written, so "evidence-linked"
#: means a checked comparison rather than a referenced id.
#:
#: YEAR is absent from the catalog row — measured, A仓 holds no publication year
#: anywhere — so there is no field for a YEAR declaration to equal, and the
#: writer refuses it rather than storing an unverifiable sentence.
CATALOG_FIELD_FOR: Dict[str, Optional[str]] = {
    "AUTHOR": "author",
    "TITLE": "title",
    "PUBLICATION": "publisher",
    "IDENTIFIER": "isbn",
    "YEAR": None,
}

#: Field names a source annotation may not grow. Each is a judgement about the
#: source rather than a fact about a record. The first four are the review
#: spec's artifact ban.
PAPER_BANNED_FIELDS = ("importance", "quality", "truth", "credibility",
                       "confidence_score", "authority_score", "reputation",
                       "ranking", "significance", "contribution_score")


class SourceType(str, Enum):
    BOOK = "BOOK"
    PAPER = "PAPER"
    ARTICLE = "ARTICLE"
    REPORT = "REPORT"
    ARCHIVE = "ARCHIVE"


class StatementType(str, Enum):
    AUTHOR = "AUTHOR"
    TITLE = "TITLE"
    PUBLICATION = "PUBLICATION"
    YEAR = "YEAR"
    IDENTIFIER = "IDENTIFIER"


class PaperStatus(str, Enum):
    """No VERIFIED, no CONFIRMED, no APPROVED.

    `VERIFIED` is the success value of `ku_verification.verification_status`;
    `CONFIRMED` and `APPROVED` are two more words for that same judgement. A
    source annotation is not a verified proposition, and this stage has no
    authority to approve anything.
    """

    GENERATED = "GENERATED"
    SUPPORTED = "SUPPORTED"
    REJECTED = "REJECTED"


#: Both SUPPORTED and REJECTED are final. A仓 corrects by appending a new
#: candidate under a new hash, never by downgrading one in place — the same rule
#: 077, 078 and 079 freeze against.
LEGAL_STATUS_TRANSITIONS: Dict[PaperStatus, frozenset] = {
    PaperStatus.GENERATED: frozenset({PaperStatus.SUPPORTED,
                                      PaperStatus.REJECTED}),
    PaperStatus.SUPPORTED: frozenset(),
    PaperStatus.REJECTED: frozenset(),
}


class PaperViolation(Exception):
    """Raised on a forbidden source-annotation operation."""


class PaperPrecondition(Exception):
    """A candidate may not be written as given; nothing was written."""


# ── identity ─────────────────────────────────────────────────────────────────

def paper_id(source_version_id: str, book_source_id: str, source_type: str,
             extractor_version: str) -> str:
    """`psc_<sha256(...)[:12]>` — step 1.

    No declared fields: this is the identity of the *annotation of this source*,
    matching the P5.0 pattern where `id` excludes content and the hash includes
    it.
    """
    digest = hashlib.sha256(
        f"{source_version_id}|{book_source_id}|{source_type}"
        f"|{extractor_version}".encode("utf-8")).hexdigest()
    return f"psc_{digest[:12]}"


def paper_hash(source_version_id: str, book_source_id: str, source_type: str,
               title: str, authors: Sequence[str],
               publication_year: Optional[int], publisher: Optional[str],
               doi: Optional[str], isbn: Optional[str],
               extractor_version: str) -> str:
    """`psh_<sha256(...)[:16]>` — step 2, the replay identity.

    Covers every declared field the candidate stores, publisher included, which
    the review spec's §5 omitted. `authors` is joined **in order**: first author
    and corresponding author are facts, so sorting them away would merge two
    genuinely different annotations into one hash.

    Evidence is deliberately absent. See the module docstring.
    """
    ordered_authors = "|".join(authors)
    digest = hashlib.sha256(
        f"{source_version_id}|{book_source_id}|{source_type}|{title}"
        f"|{ordered_authors}|{publication_year}|{publisher}|{doi}|{isbn}"
        f"|{extractor_version}".encode("utf-8")).hexdigest()
    return f"psh_{digest[:16]}"


def evidence_hash(paper_id_: str, statement_type: str, declared_value: str,
                  declared_in: str, catalog_source_id: str) -> str:
    """`peh_<sha256(...)[:16]>` — the declaration's replay key.

    The spec's §5 put evidence nowhere, which left §9's claim that evidence is
    part of the replay key unsatisfiable. This is that key, and it deliberately
    sorts nothing: `declared_value` is stored verbatim, so its exact bytes are
    part of what was declared.
    """
    digest = hashlib.sha256(
        f"{paper_id_}|{statement_type}|{declared_value}|{declared_in}"
        f"|{catalog_source_id}".encode("utf-8")).hexdigest()
    return f"peh_{digest[:16]}"


# ── rows ─────────────────────────────────────────────────────────────────────

@dataclass
class PaperSourceCandidate:
    id: str
    source_version_id: str
    book_source_id: str
    source_type: str
    title: str
    authors: List[str] = field(default_factory=list)
    publication_year: Optional[int] = None
    publisher: Optional[str] = None
    doi: Optional[str] = None
    isbn: Optional[str] = None
    paper_hash: str = ""
    extractor_version: str = EXTRACTOR_VERSION
    status: str = PaperStatus.GENERATED.value
    created_at: str = PAPER_VERSION


@dataclass
class PaperEvidence:
    id: str
    paper_id: str
    statement_type: str
    declared_value: str
    declared_in: str
    catalog_source_id: str
    evidence_hash: str = ""
    created_at: str = PAPER_VERSION


PAPER_CANDIDATE_COLUMNS = (
    "id", "source_version_id", "book_source_id", "source_type", "title",
    "authors", "publication_year", "publisher", "doi", "isbn", "paper_hash",
    "extractor_version", "status", "created_at")

PAPER_EVIDENCE_COLUMNS = (
    "id", "paper_id", "statement_type", "declared_value", "declared_in",
    "catalog_source_id", "evidence_hash", "created_at")

#: created_at carries DEFAULT now() in 080, so the insert omits it: the database
#: stamps it, and a replay cannot supply a timestamp that disagrees with the
#: stored row.
PAPER_CANDIDATE_INSERT_COLUMNS = tuple(
    c for c in PAPER_CANDIDATE_COLUMNS if c != "created_at")
PAPER_EVIDENCE_INSERT_COLUMNS = tuple(
    c for c in PAPER_EVIDENCE_COLUMNS if c != "created_at")


# ── the annotation ───────────────────────────────────────────────────────────

class PaperBuilder:
    """Composes a source annotation out of a catalog row and a source version.

    Reads the **real** `book_source` row out of the store rather than taking
    literals from a caller. That is what makes the declaration checkable: if the
    candidate's title did not come from the record, the comparison in
    `declaration_matches_catalog` would have nothing honest to compare against.
    """

    def __init__(self, ingestion_pipeline):
        self.store = ingestion_pipeline.store

    def catalog_of(self, book_source_id: str):
        """The catalog row, or None."""
        return self.store.book_sources.get(book_source_id)

    def build(self, source_version_id: str, source_type: str,
              extractor_version: str,
              overrides: Optional[Dict] = None) -> PaperSourceCandidate:
        """Build the candidate for a source version, from its own catalog row.

        `overrides` may restate any declared field. It exists so a test can
        assert that a value which disagrees with the record is refused, not so a
        caller can quietly write something the record does not say.
        """
        if source_type not in SOURCE_TYPES:
            raise PaperPrecondition(
                f"{source_type} is not a source type A仓 may record; only "
                f"{', '.join(SOURCE_TYPES)} are in 080. {FORBIDDEN_SOURCE_TYPE} "
                "is absent by design: an unreadable source is a read state, not "
                "a fact.")
        version = self.store.source_versions.get(source_version_id)
        if version is None:
            raise PaperPrecondition(
                f"{source_version_id} is not a known source version.")
        catalog = self.catalog_of(version.book_source_id)
        if catalog is None:
            raise PaperPrecondition(
                f"{version.book_source_id} is not a known catalog row; a "
                "source annotation is about a record, so the record must exist.")
        values = {
            "title": catalog.title,
            # Verbatim, one element. Splitting the author string is author
            # identity resolution, which LIMITATION-2 puts out of scope.
            "authors": [catalog.author] if catalog.author else [],
            "publication_year": None,
            "publisher": catalog.publisher,
            "doi": None,
            "isbn": catalog.isbn,
        }
        if overrides:
            values.update(overrides)
        return PaperSourceCandidate(
            id=paper_id(source_version_id, version.book_source_id, source_type,
                        extractor_version),
            source_version_id=source_version_id,
            book_source_id=version.book_source_id,
            source_type=source_type,
            title=values["title"],
            authors=list(values["authors"]),
            publication_year=values["publication_year"],
            publisher=values["publisher"],
            doi=values["doi"],
            isbn=values["isbn"],
            paper_hash=paper_hash(
                source_version_id, version.book_source_id, source_type,
                values["title"], values["authors"],
                values["publication_year"], values["publisher"], values["doi"],
                values["isbn"], extractor_version),
            extractor_version=extractor_version,
        )

    def declaration(self, candidate: PaperSourceCandidate,
                    statement_type: str,
                    declared_in: str = CATALOG_DECLARATION) -> PaperEvidence:
        """Build one declaration for a candidate, reading the catalog field.

        The value comes out of the record, never from the caller. A declaration
        whose value the record does not state cannot be expressed through this
        method at all, which is the point: the strongest guard on a fabricated
        quote is not being able to type one.
        """
        if statement_type not in STATEMENT_TYPES:
            raise PaperPrecondition(
                f"{statement_type} is not a statement type in 080.")
        if declared_in not in DECLARED_IN:
            raise PaperPrecondition(
                f"{declared_in} is not a kind of declaring record in 080.")
        catalog = self.catalog_of(candidate.book_source_id)
        if catalog is None:
            raise PaperPrecondition(
                f"{candidate.book_source_id} is not a known catalog row.")
        field_name = CATALOG_FIELD_FOR[statement_type]
        if field_name is None:
            raise PaperPrecondition(
                f"{statement_type} cannot be declared from a catalog row: it has "
                f"no {statement_type.lower()} field to read, so there is nothing "
                "to check a declaration against. Writing one would store an "
                "unverifiable sentence.")
        value = getattr(catalog, field_name, None)
        if not value:
            raise PaperPrecondition(
                f"the catalog row states no {field_name}, so there is no "
                f"{statement_type} declaration to record.")
        fingerprint = evidence_hash(candidate.id, statement_type, str(value),
                                    declared_in, candidate.book_source_id)
        return PaperEvidence(
            # A declaration has no sub-structure, so its replay key is also its
            # id: one row, one identity, and a re-run collides on UNIQUE rather
            # than appending a near-duplicate.
            id=fingerprint,
            paper_id=candidate.id,
            statement_type=statement_type,
            declared_value=str(value),
            declared_in=declared_in,
            catalog_source_id=candidate.book_source_id,
            evidence_hash=fingerprint,
        )


def declaration_matches_catalog(declaration: PaperEvidence, catalog) -> bool:
    """Does the declaring record actually state this?

    The traceability gate, expressed as one comparison. The foreign key proves
    the record exists; this proves the sentence about it is what the record
    says. A `declared_value` that drifts from its record is not evidence of
    anything, so it is refused rather than stored.
    """
    if catalog is None:
        return False
    field_name = CATALOG_FIELD_FOR.get(declaration.statement_type)
    if field_name is None:
        return False
    actual = getattr(catalog, field_name, None)
    return actual is not None and str(actual) == declaration.declared_value


def transition(candidate: PaperSourceCandidate, target: PaperStatus) -> None:
    """The only way a candidate's status changes.

    Both SUPPORTED and REJECTED are final, so a correction is a new candidate
    under a new hash.
    """
    current = PaperStatus(candidate.status)
    if target not in LEGAL_STATUS_TRANSITIONS[current]:
        raise PaperViolation(
            f"{current.value} -> {target.value} is not a legal status "
            "transition; a supported annotation is final and A仓 corrects by "
            "appending a new candidate.")
    candidate.status = target.value


# ── durability ───────────────────────────────────────────────────────────────

PAPER_TABLES = ("paper_source_candidate", "paper_evidence")

#: The bucket is NOT called `papers` or `evidence`. IdentitySink already maps
#: `reading_evidence` to a bucket named `evidence`, and two tables sharing a
#: bucket would mix frozen evidence rows with this stage's declarations in one
#: dict — which surfaces much later, on a report, as an AttributeError with no
#: hint that a name was shared.
_PAPER_BUCKETS: Dict[str, str] = {
    "paper_source_candidate": "paper_candidates",
    "paper_evidence": "paper_declarations",
}

_PAPER_ROW_TYPES: Dict[str, type] = {
    "paper_source_candidate": PaperSourceCandidate,
    "paper_evidence": PaperEvidence,
}


class PaperSink(IdentitySink):
    """Every sink up to P6, plus the two source-annotation tables.

    Inherits so the staging discipline stays in one place, and so a declaration
    cannot land without its candidate in the same store.
    """

    TABLES = IdentitySink.TABLES + PAPER_TABLES
    ROW_TYPES = {**IdentitySink.ROW_TYPES, **_PAPER_ROW_TYPES}
    ROW_BUCKETS = {**IdentitySink.ROW_BUCKETS, **_PAPER_BUCKETS}

    def __init__(self, fail_after: Optional[int] = None):
        super().__init__(fail_after=fail_after)
        self.paper_candidates: Dict[str, PaperSourceCandidate] = {}
        self.paper_declarations: Dict[str, PaperEvidence] = {}

    def commit(self, pending: Sequence[Tuple[str, Dict]]) -> None:
        staged: Dict[str, Dict[str, Dict]] = {
            table: {} for table in self.TABLES}
        for index, (table, row) in enumerate(pending):
            if self.fail_after is not None and index >= self.fail_after:
                self.rollbacks += 1
                raise RuntimeError(f"injected failure at write {index} ({table})")
            if table not in staged:
                raise PaperViolation(f"unknown table {table}")
            staged[table][row["id"]] = row
        for table, rows in staged.items():
            row_type = self.ROW_TYPES[table]
            getattr(self, self.ROW_BUCKETS[table]).update(
                {key: row_type(**value) for key, value in rows.items()})
        self.commits += 1

    def reload(self) -> Dict[str, object]:
        reloaded = super().reload()
        for table in PAPER_TABLES:
            reloaded[table] = dict(getattr(self, self.ROW_BUCKETS[table]))
        return reloaded


class PaperWriter:
    """Appends source annotations and their declarations. Holds no path
    upstream."""

    def __init__(self, ingestion_pipeline, sink: PaperSink):
        self.store = ingestion_pipeline.store
        self.builder = PaperBuilder(ingestion_pipeline)
        self.sink = sink

    # ── gates ──────────────────────────────────────────────────────────────

    def candidate_preconditions(self, candidate: PaperSourceCandidate
                                ) -> Tuple[bool, List[str]]:
        """Everything that must hold before the transaction opens."""
        failed: List[str] = []
        if candidate.source_type not in SOURCE_TYPES:
            failed.append("SOURCE_TYPE_NOT_AUTHORISED")
        if not candidate.authors:
            failed.append("NO_AUTHORS")
        if candidate.source_version_id not in self.store.source_versions:
            failed.append("NO_SUCH_SOURCE_VERSION")
        if candidate.book_source_id not in self.store.book_sources:
            failed.append("NO_SUCH_CATALOG_ROW")
        version = self.store.source_versions.get(candidate.source_version_id)
        if version is not None and \
                version.book_source_id != candidate.book_source_id:
            # 080's composite key enforces this too; the check is kept because it
            # reports a readable reason instead of a constraint name.
            failed.append("CROSS_SOURCE_CATALOG_ROW")
        catalog = self.builder.catalog_of(candidate.book_source_id)
        if catalog is None or catalog.title != candidate.title:
            failed.append("TITLE_NOT_FROM_RECORD")
        return not failed, failed

    def declaration_preconditions(self, declaration: PaperEvidence,
                                  candidate: Optional[PaperSourceCandidate] = None
                                  ) -> Tuple[bool, List[str]]:
        """Everything a declaration must satisfy before it is written.

        `candidate` is the candidate it will be written under, when that is
        already known. Without it the linkage check falls back to the stored
        rows, which is the right behaviour when re-checking something already
        written and the wrong one when the candidate is about to be written in
        the same transaction.
        """
        failed: List[str] = []
        if declaration.statement_type not in STATEMENT_TYPES:
            failed.append("STATEMENT_TYPE_NOT_AUTHORISED")
        if declaration.declared_in not in DECLARED_IN:
            failed.append("DECLARED_IN_NOT_AUTHORISED")
        target = candidate or self.sink.paper_candidates.get(
            declaration.paper_id)
        if target is None:
            failed.append("NO_SUCH_CANDIDATE")
        if not declaration.declared_value:
            failed.append("EMPTY_DECLARED_VALUE")
        if target is not None and \
                declaration.catalog_source_id != target.book_source_id:
            failed.append("DECLARATION_OTHER_CATALOG_ROW")
        catalog = self.builder.catalog_of(declaration.catalog_source_id)
        if not declaration_matches_catalog(declaration, catalog):
            # The gate that makes "evidence-linked" mean something: the record
            # has to actually say this.
            failed.append("DECLARATION_NOT_IN_RECORD")
        return not failed, failed

    # ── persistence ────────────────────────────────────────────────────────

    def write(self, candidate: PaperSourceCandidate,
              declarations: Sequence[PaperEvidence] = ()
              ) -> PaperSourceCandidate:
        """One candidate and all its declarations, in one transaction.

        The candidate goes first so the declarations' foreign key resolves, and
        both are in the same transaction so a failure leaves neither. There is
        no reachable state with a declaration and no candidate.

        A replay is a no-op for the candidate row but **not** for declarations.
        Evidence is an append-only layer under the source, so "we already have
        this source" must not silently swallow "here is a declaration for it".
        Each declaration carries its own UNIQUE fingerprint, so writing one that
        is already stored writes nothing.

        Returns the **stored** object, not the one passed in — the copy-on-write
        shape P4.1, P5.0, 078 and 079 all use. Mutating the original would
        change an object the store does not see.
        """
        ok, failed = self.candidate_preconditions(candidate)
        if not ok:
            raise PaperPrecondition(
                f"{candidate.id} may not be written: {', '.join(failed)}.")
        for declaration in declarations:
            if declaration.paper_id != candidate.id:
                raise PaperPrecondition(
                    f"{declaration.id} names {declaration.paper_id}, not "
                    f"{candidate.id}; a declaration must belong to the candidate "
                    "it is written under.")
            ok, failed = self.declaration_preconditions(declaration, candidate)
            if not ok:
                raise PaperPrecondition(
                    f"{declaration.id} may not be written: "
                    f"{', '.join(failed)}.")
        if candidate.id in self.sink.paper_candidates:
            self._append_declarations(declarations)
            return self.sink.paper_candidates[candidate.id]
        try:
            with FreezeTransaction(self.sink) as tx:
                tx.write("paper_source_candidate", dict(candidate.__dict__))
                for declaration in declarations:
                    tx.write("paper_evidence", dict(declaration.__dict__))
        except Exception as error:
            raise PaperViolation(
                f"{candidate.id} was not written: {error}") from error
        return self.sink.paper_candidates[candidate.id]

    def _append_declarations(self, declarations: Sequence[PaperEvidence]) -> None:
        """Write only the declarations not already stored, in one transaction.

        Every statement is idempotent by fingerprint, so this is safe to call on
        a replay — but it still has to be transactional, or a failure partway
        through a batch would leave the earlier declarations written.
        """
        pending = [d for d in declarations
                   if d.id not in self.sink.paper_declarations]
        if not pending:
            return
        try:
            with FreezeTransaction(self.sink) as tx:
                for declaration in pending:
                    tx.write("paper_evidence", dict(declaration.__dict__))
        except Exception as error:
            raise PaperViolation(
                f"declarations were not written: {error}") from error

    # ── lifecycle ──────────────────────────────────────────────────────────

    def support(self, paper_id_: str) -> PaperSourceCandidate:
        """GENERATED -> SUPPORTED, only with at least one declaration."""
        candidate = self.sink.paper_candidates[paper_id_]
        if not self.declarations_of(paper_id_):
            raise PaperPrecondition(
                f"{paper_id_} has no declaration; a source annotation with "
                "nothing the record actually states cannot be supported.")
        transition(candidate, PaperStatus.SUPPORTED)
        return candidate

    def reject(self, paper_id_: str) -> PaperSourceCandidate:
        """GENERATED -> REJECTED. Not available from SUPPORTED."""
        candidate = self.sink.paper_candidates[paper_id_]
        transition(candidate, PaperStatus.REJECTED)
        return candidate

    # ── immutability ───────────────────────────────────────────────────────

    def update_candidate(self, paper_id_: str, **changes) -> None:
        raise PaperViolation(
            f"{paper_id_} cannot be updated; a correction is a new candidate "
            "under a new hash, never an edit of this one.")

    def delete_candidate(self, paper_id_: str) -> None:
        raise PaperViolation(
            "A source annotation cannot be deleted. One that is no longer "
            "supported is REJECTED, which keeps the record and the reason.")

    def rate_source(self, paper_id_: str, **scores) -> None:
        raise PaperViolation(
            "A source annotation records what a record states, not how good the "
            "source is. Importance, quality and credibility are B仓 judgements.")

    def rank_sources(self, *paper_ids: str) -> None:
        raise PaperViolation(
            "A仓 does not rank sources; ordering by importance is a B仓 "
            "judgement.")

    def approve(self, paper_id_: str) -> None:
        raise PaperViolation(
            "A source annotation has no APPROVED state; A仓 does not approve "
            "sources.")

    def update_verification(self, *args, **kwargs) -> None:
        raise PaperViolation("This layer never touches a verification.")

    # ── queries ────────────────────────────────────────────────────────────

    def declarations_of(self, paper_id_: str) -> List[PaperEvidence]:
        return sorted((d for d in self.sink.paper_declarations.values()
                       if d.paper_id == paper_id_),
                      key=lambda d: (d.statement_type, d.id))

    def orphan_declarations(self) -> List[str]:
        return sorted(d.id for d in self.sink.paper_declarations.values()
                      if d.paper_id not in self.sink.paper_candidates)

    def unsourced_declarations(self) -> List[str]:
        """Declarations the catalog record does not actually state."""
        wrong: List[str] = []
        for declaration in self.sink.paper_declarations.values():
            catalog = self.builder.catalog_of(declaration.catalog_source_id)
            if not declaration_matches_catalog(declaration, catalog):
                wrong.append(declaration.id)
        return sorted(wrong)

    def cross_source_candidates(self) -> List[str]:
        wrong: List[str] = []
        for candidate in self.sink.paper_candidates.values():
            version = self.store.source_versions.get(candidate.source_version_id)
            if version is None or \
                    version.book_source_id != candidate.book_source_id:
                wrong.append(candidate.id)
        return sorted(set(wrong))

    def unauthorised_type_rows(self) -> List[str]:
        return sorted(c.id for c in self.sink.paper_candidates.values()
                      if c.source_type not in SOURCE_TYPES)

    def duplicate_hashes(self) -> List[str]:
        seen: Dict[str, int] = {}
        for candidate in self.sink.paper_candidates.values():
            seen[candidate.paper_hash] = seen.get(candidate.paper_hash, 0) + 1
        for declaration in self.sink.paper_declarations.values():
            seen[declaration.evidence_hash] = seen.get(
                declaration.evidence_hash, 0) + 1
        return sorted(h for h, count in seen.items() if count > 1)

    def pilot_rows(self) -> List[str]:
        return sorted(c.id for c in self.sink.paper_candidates.values()
                      if c.extractor_version == PILOT_DECLARED_VERSION)

    def extracted_rows(self) -> List[str]:
        return sorted(c.id for c in self.sink.paper_candidates.values()
                      if c.extractor_version != PILOT_DECLARED_VERSION)

    def traceability_percent(self) -> float:
        """candidate -> catalog row, and declaration -> the field it names.

        Counted over declarations, not over ids: "the evidence exists" is a
        foreign key, and the thing worth measuring is whether each sentence
        about the record is what the record says.
        """
        total = 0
        traced = 0
        for declaration in self.sink.paper_declarations.values():
            total += 1
            catalog = self.builder.catalog_of(declaration.catalog_source_id)
            candidate = self.sink.paper_candidates.get(declaration.paper_id)
            if candidate is None or catalog is None:
                continue
            if catalog.id != candidate.book_source_id:
                continue
            if declaration_matches_catalog(declaration, catalog):
                traced += 1
        return round(100.0 * traced / total, 2) if total else 0.0

    def declaration_coverage(self) -> Dict[str, bool]:
        """Which statement types the catalog row can actually support.

        YEAR is expected False here, and that is not a gap to be filled: A仓
        holds no publication year, so there is no field for a YEAR declaration
        to equal. Reported rather than hidden.
        """
        covered: Dict[str, bool] = {}
        stored = {d.statement_type for d in self.sink.paper_declarations.values()}
        for statement_type in STATEMENT_TYPES:
            covered[statement_type] = statement_type in stored
        return covered


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

    created_at is absent from `columns`: 080 declares DEFAULT now(), so the
    database stamps it and a replay cannot supply a timestamp that disagrees
    with the stored row.
    """
    return ",".join(_literal(row.get(c)) for c in columns)


def emit_paper_sql(candidates, declarations) -> str:
    """Both tables as one transaction, candidate before declarations.

    Every statement is ON CONFLICT DO NOTHING, so a replay writes nothing.
    """
    lines = ["BEGIN;", "SET search_path TO stratum, public;"]
    for key in sorted(candidates):
        row = dict(candidates[key].__dict__)
        lines.append(
            f"INSERT INTO paper_source_candidate "
            f"({','.join(PAPER_CANDIDATE_INSERT_COLUMNS)}) "
            f"VALUES ({_values(row, PAPER_CANDIDATE_INSERT_COLUMNS)}) "
            f"ON CONFLICT (paper_hash) DO NOTHING;")
    for key in sorted(declarations):
        row = dict(declarations[key].__dict__)
        lines.append(
            f"INSERT INTO paper_evidence "
            f"({','.join(PAPER_EVIDENCE_INSERT_COLUMNS)}) "
            f"VALUES ({_values(row, PAPER_EVIDENCE_INSERT_COLUMNS)}) "
            f"ON CONFLICT (evidence_hash) DO NOTHING;")
    lines.append("COMMIT;")
    return "\n".join(lines) + "\n"


def banned_field_report() -> Dict[str, List[str]]:
    """Which banned field names appear anywhere in this stage.

    Structural: the row dataclasses, not a word scan of the source. A source
    annotation that grew an `importance` column would be a source annotation
    making a judgement, and this is where that is noticed.
    """
    rows: Dict[str, List[str]] = {}
    for name in PAPER_BANNED_FIELDS:
        hits = []
        for row_type in (PaperSourceCandidate, PaperEvidence):
            if hasattr(row_type, name):
                hits.append(f"{row_type.__name__}.{name}")
        rows[name] = hits
    return rows


#: Frozen notes for the artifact. Kept as data so the runner cannot report a
#: limitation the module has stopped honouring.
PAPER_NOTES = {
    "SOURCE_TYPES": list(SOURCE_TYPES),
    "FORBIDDEN_SOURCE_TYPE": FORBIDDEN_SOURCE_TYPE,
    "STATEMENT_TYPES": list(STATEMENT_TYPES),
    "DECLARED_IN": list(DECLARED_IN),
    "CATALOG_FIELD_FOR": {k: v for k, v in CATALOG_FIELD_FOR.items()},
    "STATE_MACHINE": "GENERATED -> SUPPORTED | REJECTED; both terminal",
    "EVIDENCE_ANCHOR": (
        "the book_source catalog row, by foreign key; declaration_by_text_span "
        "is UNTESTED because no span in this corpus declares source metadata"),
    "DB_GUARANTEES": [
        "foreign key integrity (source_version, book_source, candidate)",
        "the candidate's catalog row is the one its version was ingested from",
        "source_type closed, with no UNKNOWN",
        "status closed, with no VERIFIED and no APPROVED",
        "authors non-empty",
        "statement_type and declared_in vocabularies closed",
        "replay uniqueness for both the candidate and the declaration",
    ],
    "DB_DOES_NOT_GUARANTEE": [
        "the state machine: a CHECK cannot read a column's previous value, so a "
        "raw UPDATE can still move SUPPORTED back to GENERATED",
        "that declared_value is what the catalog record states: the foreign key "
        "proves the record exists, not that the sentence is true",
        "publication_year sanity: an unbounded INTEGER, because A仓 holds no "
        "year to check it against",
    ],
    "PILOT_SCOPE": (
        "source metadata persistence, declaration traceability and replay; "
        "author correctness and academic quality are not measured and no "
        "extractor ships in this stage"),
}