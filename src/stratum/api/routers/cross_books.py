"""P14 Cross-Book Intelligence API endpoints.

Thin adapter over BU2P14Runner and BU2CrossBookQuery services.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from stratum.common import jwt_auth, now_utc, now_utc_dt, generate_ulid
from stratum.db import query, read
from stratum.services.bu_v2_crossbook_entrypoint import BU2P14Runner
from stratum.services.bu_v2_crossbook_query import BU2CrossBookQuery
from stratum.services.bu_v2_crossbook_collection import BU2CrossBookCollectionManager, CrossBookCollection
from stratum.services.bu_v2_crossbook_synthesis import BU2CrossBookSynthesisBuilder

router = APIRouter(prefix="/api/v1/cross-books", tags=["cross-books"])


# ── Models ──

class CollectionItem(BaseModel):
    collection_id: str
    name: str
    description: str
    book_ids: list[str]
    created_at: str


class ConceptRelationItem(BaseModel):
    relation_id: str
    source_book_id: str
    target_book_id: str
    source_concept_id: str
    target_concept_id: str
    relation: str
    confidence: float
    evidence: list[str]


class ThesisRelationItem(BaseModel):
    relation_id: str
    source_book_id: str
    target_book_id: str
    source_thesis: str
    target_thesis: str
    relation: str
    confidence: float
    evidence: list[str]


class ArgumentRelationItem(BaseModel):
    relation_id: str
    source_book_id: str
    target_book_id: str
    source_argument: str
    target_argument: str
    relation: str
    confidence: float
    evidence: list[str]


class ContradictionItem(BaseModel):
    contradiction_id: str
    book_a_id: str
    book_b_id: str
    type: str
    element_a: str
    element_b: str
    description: str
    confidence: float
    evidence: list[str]


class KnowledgeGapItem(BaseModel):
    gap_id: str
    type: str
    description: str
    affected_books: list[str]
    related_concepts: list[str]
    confidence: float


class CrossBookOverview(BaseModel):
    collection_id: str
    name: str
    books: list[dict]
    concept_relations: int
    thesis_relations: int
    argument_relations: int
    mechanism_relations: int
    evidence_relations: int
    contradictions: int
    knowledge_gaps: int


class PairwiseComparison(BaseModel):
    book_a_id: str
    book_b_id: str
    concept_relations: list[ConceptRelationItem]
    thesis_relations: list[ThesisRelationItem]
    argument_relations: list[ArgumentRelationItem]
    contradictions: list[ContradictionItem]


class ExpressionResponse(BaseModel):
    collection_id: str
    collection_name: str
    book_count: int
    concept_summary: str
    thesis_summary: str
    argument_summary: str
    contradiction_summary: str
    gap_summary: str
    synthesis: str
    pairwise_comparisons: str
    quality: str


class QueryRequest(BaseModel):
    query_type: str  # concepts, contradictions, arguments, gaps, pairwise
    filter: dict | None = None


class QueryResponse(BaseModel):
    items: list
    total: int
    query: str
    traceability: dict


# ── Helper: load understanding ──

def _understanding_row(collection_id: str):
    """crossbook_understandings row exposed under the model's field names."""
    from stratum.services.bu_v2_p14_loader import understanding_row_view

    return understanding_row_view(
        read("crossbook_understandings", collection_id, id_column="collection_id")
    )


# ── Helper: load collection ──

async def _load_collection(collection_id: str, user_id: str):
    """Load collection and verify access."""
    manager = BU2CrossBookCollectionManager()
    collection = read("crossbook_collections", collection_id)
    if not collection:
        raise HTTPException(404, "Collection not found")
    # Verify user owns all books in collection
    book_ids = collection["book_ids"]
    for bid in book_ids:
        # Check substrate ownership
        row = query(
            "SELECT 1 FROM stratum.substrates WHERE id=%(bid)s AND user_id IN (%(uid)s, %(huid)s)",
            {"bid": bid, "uid": user_id, "huid": user_id},
        )
        if not row:
            raise HTTPException(403, f"No access to book {bid}")
    return collection


# ── Routes ──

@router.get("", response_model=list[CollectionItem])
async def list_collections(user_id: str = Depends(jwt_auth)):
    """List cross-book collections for the current user."""
    rows = query(
        """
        SELECT id, name, description, book_ids, created_at
        FROM stratum.crossbook_collections
        WHERE user_id IN (%(uid)s, %(huid)s)
        ORDER BY created_at DESC
        """,
        {"uid": user_id, "huid": user_id},
    )
    return [
        CollectionItem(
            collection_id=r[0], name=r[1], description=r[2],
            book_ids=r[3] or [], created_at=str(r[4])
        )
        for r in rows
    ]


@router.post("", response_model=CollectionItem, status_code=201)
async def create_collection(
    body: dict, user_id: str = Depends(jwt_auth)
):
    """Create a new cross-book collection."""
    from stratum.common import generate_ulid, now_utc
    name = body.get("name")
    description = body.get("description", "")
    book_ids = body.get("book_ids", [])
    if not name or len(book_ids) < 2:
        raise HTTPException(400, "Collection requires name and at least 2 book_ids")

    # Verify ownership
    for bid in book_ids:
        row = query(
            "SELECT 1 FROM stratum.substrates WHERE id=%(bid)s AND user_id IN (%(uid)s, %(huid)s)",
            {"bid": bid, "uid": user_id, "huid": user_id},
        )
        if not row:
            raise HTTPException(403, f"No access to book {bid}")

    collection_id = f"cb_{generate_ulid()}"
    now = now_utc_dt()
    query(
        """
        INSERT INTO stratum.crossbook_collections
        (id, user_id, name, description, book_ids, created_at, updated_at)
        VALUES (%(id)s, %(uid)s, %(name)s, %(desc)s, %(bids)s, %(now)s, %(now)s)
        """,
        {"id": collection_id, "uid": user_id, "name": name, "desc": description,
         "bids": book_ids, "now": now},
    )
    return CollectionItem(
        collection_id=collection_id, name=name, description=description,
        book_ids=book_ids, created_at=str(now)
    )


@router.get("/{collection_id}", response_model=CrossBookOverview)
async def get_crossbook_overview(
    collection_id: str, user_id: str = Depends(jwt_auth)
):
    """Get cross-book understanding overview."""
    collection = await _load_collection(collection_id, user_id)

    # Load understanding
    understanding = _understanding_row(collection_id)
    if not understanding:
        raise HTTPException(404, "Cross-book understanding not found. Run P14 first.")

    return CrossBookOverview(
        collection_id=collection_id,
        name=collection["name"],
        books=[{"book_id": bid, "title": "Book " + bid} for bid in collection["book_ids"]],
        concept_relations=len(understanding.get("concept_relations", [])),
        thesis_relations=len(understanding.get("thesis_relations", [])),
        argument_relations=len(understanding.get("argument_relations", [])),
        mechanism_relations=len(understanding.get("mechanism_relations", [])),
        evidence_relations=len(understanding.get("evidence_relations", [])),
        contradictions=len(understanding.get("contradictions", [])),
        knowledge_gaps=len(understanding.get("knowledge_gaps", [])),
    )


@router.post("/{collection_id}/run")
async def run_p14(
    collection_id: str, user_id: str = Depends(jwt_auth)
):
    """Execute P14 cross-book intelligence pipeline."""
    collection_dict = await _load_collection(collection_id, user_id)
    # Convert datetime to string for Pydantic validation
    if isinstance(collection_dict.get("created_at"), datetime):
        collection_dict["created_at"] = collection_dict["created_at"].isoformat()
    from stratum.services.bu_v2_p14_loader import collection_from_row

    collection = collection_from_row(collection_dict)

    runner = BU2P14Runner(persist=True, user_id=user_id)
    result = runner.execute(collection)

    if not result.understanding:
        return {
            "status": "failed",
            "failures": result.failures,
            "stats": result.stats,
        }

    return {
        "status": "completed",
        "understanding_id": result.understanding.understanding_id,
        "stats": result.stats,
    }


@router.get("/{collection_id}/concepts", response_model=list[ConceptRelationItem])
async def get_concept_relations(
    collection_id: str,
    relation: str | None = Query(None),
    user_id: str = Depends(jwt_auth),
):
    """Get concept relations across books."""
    collection = await _load_collection(collection_id, user_id)
    understanding = _understanding_row(collection_id)
    if not understanding:
        raise HTTPException(404, "Run P14 first")

    items = []
    for r in understanding.get("concept_relations", []):
        if relation and r.get("relation") != relation:
            continue
        items.append(ConceptRelationItem(
            relation_id=r.get("relation_id", ""),
            source_book_id=r.get("source_book_id", ""),
            target_book_id=r.get("target_book_id", ""),
            source_concept_id=r.get("source_concept_id", ""),
            target_concept_id=r.get("target_concept_id", ""),
            relation=r.get("relation", ""),
            confidence=float(r.get("confidence", 0)),
            evidence=r.get("evidence", []),
        ))
    return items


@router.get("/{collection_id}/theses", response_model=list[ThesisRelationItem])
async def get_thesis_relations(
    collection_id: str,
    relation: str | None = Query(None),
    user_id: str = Depends(jwt_auth),
):
    """Get thesis relations across books."""
    collection = await _load_collection(collection_id, user_id)
    understanding = _understanding_row(collection_id)
    if not understanding:
        raise HTTPException(404, "Run P14 first")

    items = []
    for r in understanding.get("thesis_relations", []):
        if relation and r.get("relation") != relation:
            continue
        items.append(ThesisRelationItem(
            relation_id=r.get("relation_id", ""),
            source_book_id=r.get("source_book_id", ""),
            target_book_id=r.get("target_book_id", ""),
            source_thesis=r.get("source_thesis", ""),
            target_thesis=r.get("target_thesis", ""),
            relation=r.get("relation", ""),
            confidence=float(r.get("confidence", 0)),
            evidence=r.get("evidence", []),
        ))
    return items


@router.get("/{collection_id}/arguments", response_model=list[ArgumentRelationItem])
async def get_argument_relations(
    collection_id: str,
    relation: str | None = Query(None),
    user_id: str = Depends(jwt_auth),
):
    """Get argument relations across books."""
    collection = await _load_collection(collection_id, user_id)
    understanding = _understanding_row(collection_id)
    if not understanding:
        raise HTTPException(404, "Run P14 first")

    items = []
    for r in understanding.get("argument_relations", []):
        if relation and r.get("relation") != relation:
            continue
        items.append(ArgumentRelationItem(
            relation_id=r.get("relation_id", ""),
            source_book_id=r.get("source_book_id", ""),
            target_book_id=r.get("target_book_id", ""),
            source_argument=r.get("source_argument", ""),
            target_argument=r.get("target_argument", ""),
            relation=r.get("relation", ""),
            confidence=float(r.get("confidence", 0)),
            evidence=r.get("evidence", []),
        ))
    return items


@router.get("/{collection_id}/contradictions", response_model=list[ContradictionItem])
async def get_contradictions(
    collection_id: str,
    type: str | None = Query(None),
    user_id: str = Depends(jwt_auth),
):
    """Get contradictions across books."""
    collection = await _load_collection(collection_id, user_id)
    understanding = _understanding_row(collection_id)
    if not understanding:
        raise HTTPException(404, "Run P14 first")

    items = []
    for c in understanding.get("contradictions", []):
        if type and c.get("type") != type:
            continue
        items.append(ContradictionItem(
            contradiction_id=c.get("contradiction_id", ""),
            book_a_id=c.get("book_a_id", ""),
            book_b_id=c.get("book_b_id", ""),
            type=c.get("type", ""),
            element_a=c.get("element_a", ""),
            element_b=c.get("element_b", ""),
            description=c.get("description", ""),
            confidence=float(c.get("confidence", 0)),
            evidence=c.get("evidence", []),
        ))
    return items


@router.get("/{collection_id}/gaps", response_model=list[KnowledgeGapItem])
async def get_knowledge_gaps(
    collection_id: str,
    type: str | None = Query(None),
    user_id: str = Depends(jwt_auth),
):
    """Get knowledge gaps across books."""
    collection = await _load_collection(collection_id, user_id)
    understanding = _understanding_row(collection_id)
    if not understanding:
        raise HTTPException(404, "Run P14 first")

    items = []
    for g in understanding.get("knowledge_gaps", []):
        if type and g.get("type") != type:
            continue
        items.append(KnowledgeGapItem(
            gap_id=g.get("gap_id", ""),
            type=g.get("type", ""),
            description=g.get("description", ""),
            affected_books=g.get("affected_books", []),
            related_concepts=g.get("related_concepts", []),
            confidence=float(g.get("confidence", 0)),
        ))
    return items


@router.get("/{collection_id}/synthesis")
async def get_synthesis(
    collection_id: str, user_id: str = Depends(jwt_auth)
):
    """Get full cross-book synthesis."""
    collection = await _load_collection(collection_id, user_id)
    understanding = _understanding_row(collection_id)
    if not understanding:
        raise HTTPException(404, "Run P14 first")

    return understanding.get("synthesis", {})


@router.get("/{collection_id}/expression", response_model=ExpressionResponse)
async def get_expression(
    collection_id: str, user_id: str = Depends(jwt_auth)
):
    """Get human-readable cross-book expression."""
    collection = await _load_collection(collection_id, user_id)
    understanding = _understanding_row(collection_id)
    if not understanding:
        raise HTTPException(404, "Run P14 first")

    # Generate expression using the generator
    from stratum.services.bu_v2_crossbook_expression import BU2CrossBookExpressionGenerator
    from stratum.knowledge.bu_v2_models import CrossBookUnderstanding

    cb_understanding = CrossBookUnderstanding(**understanding)
    generator = BU2CrossBookExpressionGenerator()
    expr = generator.generate(cb_understanding)

    return ExpressionResponse(
        collection_id=expr.collection_id,
        collection_name=expr.collection_name,
        book_count=expr.book_count,
        concept_summary=expr.concept_summary,
        thesis_summary=expr.thesis_summary,
        argument_summary=expr.argument_summary,
        contradiction_summary=expr.contradiction_summary,
        gap_summary=expr.gap_summary,
        synthesis=expr.synthesis,
        pairwise_comparisons=expr.pairwise_comparisons,
        quality=expr.quality,
    )


@router.get("/{collection_id}/pairwise", response_model=list[PairwiseComparison])
async def get_pairwise(
    collection_id: str, user_id: str = Depends(jwt_auth)
):
    """Get pairwise book comparisons."""
    collection = await _load_collection(collection_id, user_id)
    understanding = _understanding_row(collection_id)
    if not understanding:
        raise HTTPException(404, "Run P14 first")

    items = []
    for comp in understanding.get("comparisons", []):
        items.append(PairwiseComparison(
            book_a_id=comp.get("book_a_id", ""),
            book_b_id=comp.get("book_b_id", ""),
            concept_relations=[
                ConceptRelationItem(**r) for r in comp.get("concept_relations", [])
            ],
            thesis_relations=[
                ThesisRelationItem(**r) for r in comp.get("thesis_relations", [])
            ],
            argument_relations=[
                ArgumentRelationItem(**r) for r in comp.get("argument_relations", [])
            ],
            contradictions=[
                ContradictionItem(**c) for c in comp.get("contradictions", [])
            ],
        ))
    return items


@router.post("/{collection_id}/query", response_model=QueryResponse)
async def query_crossbook(
    collection_id: str, body: QueryRequest, user_id: str = Depends(jwt_auth)
):
    """Execute cross-book query."""
    collection = await _load_collection(collection_id, user_id)
    understanding = _understanding_row(collection_id)
    if not understanding:
        raise HTTPException(404, "Run P14 first")

    from stratum.knowledge.bu_v2_models import CrossBookUnderstanding
    cb_understanding = CrossBookUnderstanding(**understanding)
    query_builder = BU2CrossBookQuery(cb_understanding)

    qtype = body.query_type
    filter_dict = body.filter or {}

    if qtype == "concepts":
        result = query_builder.find_shared_concepts(filter_dict.get("relation"))
    elif qtype == "contradictions":
        result = query_builder.find_contradictions(filter_dict.get("type"))
    elif qtype == "arguments":
        result = query_builder.find_crossbook_arguments(filter_dict.get("relation"))
    elif qtype == "gaps":
        result = query_builder.find_knowledge_gaps(filter_dict.get("type"))
    elif qtype == "pairwise":
        result = query_builder.compare_books(
            filter_dict.get("book_a", ""), filter_dict.get("book_b", "")
        )
    elif qtype == "synthesis":
        result = query_builder.get_crossbook_synthesis()
    else:
        raise HTTPException(400, f"Unknown query type: {qtype}")

    return QueryResponse(
        items=result.items,
        total=result.total,
        query=result.query,
        traceability=result.traceability,
    )