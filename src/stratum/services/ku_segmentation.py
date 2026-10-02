"""P2 KU 2.0 runtime — semantic boundary, context recovery, stance/scope (§§7-9, §12).

Deterministic baseline (no LLM): proposition splitting, cue-based discourse /
epistemic role detection, scope-condition-qualifier extraction, context
recovery by concept overlap, and the Qualified KU Gate checklist.

Output is a transient CandidateKU dict whose fields map 1:1 onto the existing
``stratum.knowledge_claims`` KU 2.0 columns (053) — no second KU authority is
created. LLM-backed extractors plug in via the PropositionAnalyzer protocol.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Protocol, Tuple

_ABBREV = ("e.g", "i.e", "etc", "vs", "Mr", "Mrs", "Dr", "Fig", "Eq", "Sec",
           "Ch", "Vol", "No", "St", "Prof")


def split_sentences(text: str) -> List[str]:
    """Sentence split with abbreviation guard (no sentence->KU assumption)."""
    if not text or not text.strip():
        return []
    # Protect abbreviations, then split on sentence-terminal punctuation.
    guards = {}
    guarded = text
    for i, ab in enumerate(_ABBREV):
        token = f"\x00{i}\x00"
        guards[token] = ab
        guarded = re.sub(rf"\b{re.escape(ab)}\.", token, guarded)
    parts = re.split(r"(?<=[.!?。！？])\s+", guarded.strip())
    out = []
    for p in parts:
        for token, ab in guards.items():
            p = p.replace(token, ab + ".")
        p = p.strip()
        if p:
            out.append(p)
    return out


_CONTRAST = re.compile(
    r"\s+(but|however|while|whereas|although|though|yet|nevertheless)\s+",
    re.IGNORECASE)


def split_propositions(text: str) -> List[str]:
    """Evidence -> candidate propositions (§7). One sentence may express more
    than one self-contained unit; contrastive connectors fork candidates."""
    props: List[str] = []
    for sent in split_sentences(text):
        chunks = [c.strip(" ,;") for c in _CONTRAST.split(sent) if c.strip(" ,;")]
        # _CONTRAST.split keeps the connector; re-attach it to the 2nd half.
        merged: List[str] = []
        buf = ""
        for c in chunks:
            if re.fullmatch(r"(?i)but|however|while|whereas|although|though|yet|nevertheless", c):
                buf = c + " "
                continue
            merged.append((buf + c).strip())
            buf = ""
        if len(merged) >= 2 and all(len(m) > 12 for m in merged):
            props.extend(merged)
        else:
            props.append(sent)
    return [p for p in props if p]


# ── Discourse roles (§10) ─────────────────────────────────────────────────────

_DISCOURSE_CUES: List[Tuple[str, Tuple[str, ...]]] = [
    ("QUESTION", ("?",)),
    ("DEFINITION", ("is defined as", "defined as", "refers to", "we define",
                    "by definition", "means that", "is the term for")),
    ("EVIDENCE", ("study shows", "studies show", "data show", "results show",
                  "figure", "table ", "measured", "experiment", "survey of",
                  "evidence for", "as shown in")),
    ("EXAMPLE", ("for example", "for instance", "e.g.", "consider the case",
                 "such as")),
    ("COUNTEREXAMPLE", ("counterexample", "contrary case", "fails in the case of")),
    ("ASSUMPTION", ("assume", "suppose", "assumption", "let us posit",
                    "for the sake of argument")),
    ("HYPOTHESIS", ("hypothesiz", "may explain", "conjecture", "working hypothesis")),
    ("EXCEPTION", ("with the exception", "apart from", "excluding", "except for",
                   "does not apply to")),
    ("QUALIFICATION", ("only if", "only when", "limited to", "to the extent",
                       "under conditions", "qualifies the claim")),
    ("OBJECTION", ("critics argue", "one might object", "objection", "skeptics",
                   "opponents claim")),
    ("REBUTTAL", ("this objection fails", "in reply", "rebuttal", "we respond",
                  "the evidence against this view")),
    ("APPLICATION", ("in practice", "applied to", "application to", "policymakers",
                     "to implement")),
    ("CONCLUSION", ("therefore", "in conclusion", "thus,", "hence,", "it follows")),
    ("OBSERVATION", ("we observe", "observed", "measurements", "recorded")),
]

_EPISTEMIC_CUES: List[Tuple[str, Tuple[str, ...]]] = [
    ("QUOTED_POSITION", ("argues that", "claims that", "suggests that",
                         "according to", "in the words of", '"')),
    ("HISTORICAL_POSITION", ("historically", "traditionally", "once thought",
                             "the classical view")),
    ("OPPONENT_POSITION", ("critics", "opponents", "skeptics", "rival theory")),
    ("AUTHOR_REJECTED", ("we reject", "is wrong", "refuted", "fails to account",
                         "mistaken view", "untenable")),
    ("AUTHOR_HYPOTHESIZED", ("might", "could be", "perhaps", "possibly",
                             "hypothesis")),
]


def detect_discourse_role(text: str) -> str:
    low = text.lower()
    for role, cues in _DISCOURSE_CUES:
        if any(c in low for c in cues):
            return role
    return "CLAIM"


def detect_epistemic_role(text: str) -> Tuple[str, str]:
    """Return (epistemic_role, speaker_hint). Speaker hint is the best-effort
    quoted source name or '' when the author speaks."""
    low = text.lower()
    for role, cues in _EPISTEMIC_CUES:
        if any(c in low for c in cues):
            speaker = ""
            m = re.search(r"according to ([A-Z][\w\-]+(?: [A-Z][\w\-]+)?)", text,
                              re.IGNORECASE)
            if m:
                speaker = m.group(1)
            m2 = re.search(r"([A-Z][\w\-]+(?: [A-Z][\w\-]+)?) (?:argues|claims|suggests) that", text)
            if m2:
                speaker = m2.group(1)
            return role, speaker
    return "AUTHOR_ASSERTED", ""


def assert_quote_author_separation(epistemic_role: str, speaker: str) -> None:
    """Hard gate §11: QUOTED_POSITION != AUTHOR_ASSERTED; a quote without a
    resolved speaker is a STANCE_ERROR, not an author claim."""
    if epistemic_role == "QUOTED_POSITION" and not speaker:
        raise ValueError("STANCE_ERROR: QUOTED_POSITION requires a resolved speaker.")


# ── Scope / conditions / modality / quantifier ────────────────────────────────

_CONDITION = re.compile(r"\b(if|unless|when|whenever|provided that|given that|in cases? where)\b\s+([^;.\n]{4,120})",
                        re.IGNORECASE)
_QUALIFIER_WORDS = ("usually", "generally", "often", "typically", "in most cases",
                    "for the most part", "tend to")
_EXCEPTION = re.compile(r"\b(except|apart from|excluding|with the exception of)\b\s+([^;.\n]{2,80})",
                        re.IGNORECASE)


def extract_scope_conditions(text: str) -> Dict[str, Any]:
    low = text.lower()
    conditions = [m.group(0).strip() for m in _CONDITION.finditer(text)]
    qualifiers = [w for w in _QUALIFIER_WORDS if w in low]
    exceptions = [m.group(0).strip() for m in _EXCEPTION.finditer(text)]
    if re.search(r"\b(all|every|always|never|none|no )\b", low):
        quantifier = "universal"
    elif re.search(r"\b(most|many|majority)\b", low):
        quantifier = "majority"
    elif re.search(r"\b(some|several|few|exists)\b", low):
        quantifier = "existential"
    else:
        quantifier = "unspecified"
    if re.search(r"\b(must|necessarily|inevitably)\b", low):
        modality = "necessary"
    elif re.search(r"\b(may|might|can|could|possibly|perhaps)\b", low):
        modality = "possible"
    else:
        modality = "asserted"
    return {
        "conditions": conditions,
        "qualifiers": qualifiers,
        "exceptions": exceptions,
        "quantifier": quantifier,
        "modality": modality,
    }


def _concept_tokens(text: str) -> List[str]:
    return re.findall(r"[A-Za-z][A-Za-z\-]{3,}", text.lower())


def recover_context(candidate: Dict[str, Any], prior_kus: List[Dict[str, Any]],
                    max_refs: int = 5) -> List[str]:
    """Context Recovery (§7): attach relevant prior KUs by concept overlap.
    Never ALL_PREVIOUS_TEXT (§25)."""
    mine = set(_concept_tokens(candidate.get("proposition", "")))
    scored = []
    for ku in prior_kus:
        other = set(_concept_tokens(ku.get("proposition", "")))
        overlap = mine & other
        if overlap:
            scored.append((len(overlap), ku.get("ku_id", "")))
    scored.sort(reverse=True)
    return [kid for _, kid in scored[:max_refs] if kid]


class PropositionAnalyzer(Protocol):
    def analyze(self, text: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        ...


class DeterministicAnalyzer:
    """Baseline PropositionAnalyzer: deterministic rules, fully testable.
    LLM-backed analyzers implement the same protocol for production."""

    def analyze(self, text: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        prior = context.get("prior_kus", [])
        out = []
        for prop in split_propositions(text):
            epistemic, speaker = detect_epistemic_role(prop)
            sc = extract_scope_conditions(prop)
            cand = {
                "point": prop,
                "natural_text": prop,
                "proposition": prop,
                "discourse_role": detect_discourse_role(prop),
                "argument_role": "",
                "epistemic_role": epistemic,
                "speaker": speaker,
                "stance": "quoted" if epistemic in (
                    "QUOTED_POSITION", "HISTORICAL_POSITION",
                    "OPPONENT_POSITION") else (
                    "rejected" if epistemic == "AUTHOR_REJECTED" else "author"),
                "modality": sc["modality"],
                "quantifier": sc["quantifier"],
                "scope": context.get("default_scope", {}),
                "conditions": sc["conditions"],
                "qualifiers": sc["qualifiers"],
                "exceptions": sc["exceptions"],
                "source_id": context.get("source_id", ""),
                "chapter_id": context.get("chapter_id", ""),
                "fragment_refs": context.get("fragment_refs", []),
                "page_range": context.get("page_range", []),
                "relevant_prior_kus": recover_context({"proposition": prop}, prior),
                "context_status": "recovered" if prior else "chapter_only",
                "grounding_status": "grounded" if context.get("fragment_refs") else "unverified",
            }
            out.append(cand)
        return out


# ── Qualified KU Gate (§12) ───────────────────────────────────────────────────

def qualified_ku_gate(candidate: Dict[str, Any],
                      known_concepts: Optional[List[str]] = None) -> Tuple[bool, List[str]]:
    """Return (passed, failures). Every §12 item is an explicit check."""
    failures: List[str] = []
    if not candidate.get("fragment_refs") and not candidate.get("page_range"):
        failures.append("SOURCE_GROUNDED")
    if not candidate.get("proposition", "").strip():
        failures.append("SEMANTIC_BOUNDARY_RESOLVED")
        failures.append("SEMANTICALLY_COMPLETE")
    if candidate.get("context_status") in ("", "unresolved", None):
        failures.append("CONTEXT_COMPLETE")
    if candidate.get("epistemic_role") == "QUOTED_POSITION" and not candidate.get("speaker"):
        failures.append("SPEAKER_RESOLVED")
    if not candidate.get("stance"):
        failures.append("STANCE_RESOLVED")
    if not candidate.get("scope"):
        failures.append("SCOPE_PRESERVED")
    if "conditions" not in candidate:
        failures.append("CONDITION_PRESERVED")
    if not (candidate.get("source_id") and candidate.get("chapter_id")
            and candidate.get("extraction_run_id")):
        failures.append("PROVENANCE_COMPLETE")
    if known_concepts is not None:
        hallucinated = [c for c in candidate.get("concepts", [])
                        if c not in known_concepts]
        if hallucinated:
            failures.append(f"NO_HALLUCINATED_CONTENT:{hallucinated}")
    return (len(failures) == 0, failures)
