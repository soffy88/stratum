import asyncio, asyncpg, os, json, httpx
from dotenv import load_dotenv; load_dotenv('aii/.env',override=True)
SUB='microecon_en_full_v2'; KEY=os.getenv('DEEPSEEK_API_KEY')
CONCEPTS=['Opportunity cost','Marginal cost','Investment','Demand','Net benefit','Market']
SYS=("You extract the INVARIANT CORE (本性/不变内核) that a SET of knowledge units COMMONLY express about a concept. "
     "★STRICT 命门: (1) The core must be GENUINELY SHARED — each listed KU must actually embody it. "
     "(2) Do NOT fabricate a deep-sounding core the KUs don't truly share (NO 附会/over-reaching). "
     "(3) If the KUs do NOT share one clear invariant core (e.g. the concept is used too broadly/differently), "
     "set confidence='none' and core='未发现明确共同本性' — HONESTY over depth. "
     "(4) Traceability: in embodied_by, list ONLY KUs that genuinely embody the core, each with HOW. "
     'Output JSON {"core_zh":"<不变内核, 简体>","confidence":"high|medium|none",'
     '"embodied_by":[{"ku":"<title>","how_zh":"<这个KU怎么体现的>"}],"excluded":["<体现不明确的KU title>"]}.')
async def go():
    c=await asyncpg.connect(os.getenv('DATABASE_URL'))
    async with httpx.AsyncClient(trust_env=False,timeout=60) as cli:
        for cn in CONCEPTS:
            kus=await c.fetch("""SELECT k.title, left(k.natural_text,300) snip
                FROM aii.ku_concept_onto kc JOIN aii.concept_onto cc ON kc.concept_id=cc.concept_id
                JOIN aii.ku_onto k ON kc.ku_id=k.ku_id
                WHERE cc.name=$1 AND k.substrate_id=$2
                ORDER BY (k.title ILIKE '%'||$1||'%') DESC LIMIT 12""", cn, SUB)
            body=f"Concept: {cn}\n\nKnowledge units involving it:\n"+"\n".join(f"- [{k['title']}] {k['snip']}" for k in kus)
            try:
                r=await cli.post("https://api.deepseek.com/chat/completions",headers={"Authorization":f"Bearer {KEY}"},
                    json={"model":"deepseek-v4-flash","response_format":{"type":"json_object"},
                          "messages":[{"role":"system","content":SYS},{"role":"user","content":body}]})
                j=json.loads(r.json()["choices"][0]["message"]["content"])
            except Exception as e: print(f"\n### {cn}: ERR {e}"); continue
            print(f"\n{'='*70}\n### {cn} ({len(kus)} KU) — confidence={j.get('confidence')}")
            print(f"本性: {j.get('core_zh')}")
            for e in (j.get('embodied_by') or [])[:6]: print(f"   ✓ [{e.get('ku')}] {e.get('how_zh','')[:70]}")
            if j.get('excluded'): print(f"   ✗体现不明确: {j['excluded'][:5]}")
    await c.close()
asyncio.run(go())
