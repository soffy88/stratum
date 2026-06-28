"""实证: Hearst patterns(纯规则0 LLM)抽层级关系 vs LLM判的层级边. 对照一致率/省多少LLM."""
import asyncio, os, re, sys
from pathlib import Path
from collections import defaultdict
from dotenv import load_dotenv
ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / "aii" / ".env", override=True)
sys.path.insert(0, "scripts")
from chapter_ingest import slice_chapter, SM
import asyncpg

SUB = "microecon_en_ch3"

# Hearst-style 词法模式 (capture 概念对). 关系方向: special_case_of=X是Y的特例; subsumes=Y含X; prerequisite_of=X是Y前提
_PATTERNS = [
    # special_case_of (hyponym is-a hypernym)
    (r"(?P<a>[\w\- ]{3,40}?) (?:is|are) (?:a |an |one )?(?:type|form|kind|category|class|example|special case) of (?P<b>[\w\- ]{3,40})", "special_case_of", "a_b"),
    (r"(?P<b>[\w\- ]{3,40}?) such as (?P<a>[\w\- ]{3,40})", "special_case_of", "a_b"),
    (r"(?P<a>[\w\- ]{3,40}?)(?:,| and| or) (?:other |another )(?P<b>[\w\- ]{3,40})", "special_case_of", "a_b"),
    # subsumes (hypernym includes hyponym)
    (r"(?P<b>[\w\- ]{3,40}?) (?:includes?|comprises?|consists? of|encompasses?|is composed of) (?P<a>[\w\-,  ]{3,80})", "subsumes", "b_a"),
    # prerequisite_of (a is prerequisite of b: b requires a)
    (r"(?P<b>[\w\- ]{3,40}?) (?:requires?|depends on|presupposes?|needs?) (?P<a>[\w\- ]{3,40})", "prerequisite_of", "a_b"),
    (r"(?P<a>[\w\- ]{3,40}?) (?:is|are) (?:necessary|required|needed|a prerequisite) for (?P<b>[\w\- ]{3,40})", "prerequisite_of", "a_b"),
]


def norm(s):
    return re.sub(r"\s+", " ", s.strip().lower()).rstrip("s")  # crude singularize


async def main():
    conn = await asyncpg.connect(os.getenv("DATABASE_URL"))
    # concepts of this chapter
    crows = await conn.fetch(
        """SELECT DISTINCT c.name FROM aii.ku_concept_onto kc JOIN aii.concept_onto c ON kc.concept_id=c.concept_id
           JOIN aii.ku_onto k ON kc.ku_id=k.ku_id AND k.substrate_id=$1""", SUB)
    concepts = {norm(r["name"]): r["name"] for r in crows}
    cnorms = set(concepts)

    def match_concept(span):
        n = norm(span)
        if n in cnorms:
            return concepts[n]
        # substring: span contains a concept or concept contains span tail
        for cn in cnorms:
            if cn in n or n.endswith(cn):
                return concepts[cn]
        return None

    # LLM hierarchical edges → concept pairs (via defines_concept / concepts)
    erows = await conn.fetch(
        """SELECT e.relation_type rel,
                  ka.natural_text sa, kb.natural_text sb,
                  (SELECT c.name FROM aii.ku_concept_onto x JOIN aii.concept_onto c ON x.concept_id=c.concept_id WHERE x.ku_id=e.src_id LIMIT 1) ca,
                  (SELECT c.name FROM aii.ku_concept_onto x JOIN aii.concept_onto c ON x.concept_id=c.concept_id WHERE x.ku_id=e.dst_id LIMIT 1) cb
           FROM aii.edge_onto e JOIN aii.ku_onto ka ON e.src_id=ka.ku_id JOIN aii.ku_onto kb ON e.dst_id=kb.ku_id
           WHERE e.substrate_id=$1 AND e.relation_type IN ('subsumes','special_case_of','prerequisite_of')""", SUB)
    llm_pairs = set()
    for r in erows:
        if r["ca"] and r["cb"]:
            llm_pairs.add((r["rel"], norm(r["ca"]), norm(r["cb"])))
    llm_explains = await conn.fetchval("SELECT count(*) FROM aii.edge_onto WHERE substrate_id=$1 AND relation_type='explains'", SUB)
    await conn.close()

    # Hearst over chapter source text
    text = slice_chapter(SM.read_text(encoding="utf-8", errors="replace"), 3)
    text = re.sub(r"\s+", " ", text)
    rule_pairs = set()
    rule_hits = []
    for pat, rel, order in _PATTERNS:
        for m in re.finditer(pat, text, re.I):
            ca, cb = match_concept(m.group("a")), match_concept(m.group("b"))
            if ca and cb and norm(ca) != norm(cb):
                if order == "a_b":
                    rule_pairs.add((rel, norm(ca), norm(cb)))
                else:
                    rule_pairs.add((rel, norm(cb), norm(ca)))
                rule_hits.append((rel, ca, cb, m.group(0)[:70]))

    # compare (relation-agnostic concept-pair + relation-specific)
    llm_cp = {(a, b) for _, a, b in llm_pairs}
    rule_cp = {(a, b) for _, a, b in rule_pairs}
    agree_cp = llm_cp & rule_cp
    print(f"=== HIERARCHY edges: LLM concept-pairs={len(llm_cp)}  Rule(Hearst) concept-pairs={len(rule_cp)} ===")
    print(f"agreement (same concept-pair, dir-agnostic): {len(agree_cp)}")
    print(f"rule-found LLM-missed: {len(rule_cp - llm_cp)}")
    print(f"LLM-found rule-missed: {len(llm_cp - rule_cp)}  (recall gap → need LLM or are loose)")
    print(f"\n=== Hearst rule hits (sample, concept-resolved) ===")
    for rel, ca, cb, span in rule_hits[:15]:
        mark = "✓LLM" if (norm(ca), norm(cb)) in llm_cp or (norm(cb), norm(ca)) in llm_cp else "·new"
        print(f"  [{mark}] {rel}: '{ca}' / '{cb}'   «{span}»")
    print(f"\n=== ③ explains (mechanism) edges={llm_explains}: Hearst patterns target is-a/part-of, NOT mechanism → 0 by construction ===")
    print(f"\n=== ④ cost: all-LLM=1177 candidates judged; typed: hierarchy(~52%={int(1177*0.52)}) by rule(0 LLM), only mechanism+other(~48%={int(1177*0.48)}) to LLM ===")


if __name__ == "__main__":
    asyncio.run(main())
