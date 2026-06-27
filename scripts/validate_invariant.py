import asyncio, asyncpg, os, json, httpx
from dotenv import load_dotenv; load_dotenv("/home/soffy/projects/AII/aii/.env", override=True)
KEY=os.getenv('DEEPSEEK_API_KEY')
async def essence(cli, concept, kus_text):
    SYS=("Read out the INVARIANT CORE (不变内核) these knowledge units commonly express for the concept. "
         "ONLY what they genuinely share; no fabrication. Output JSON {\"core\":\"<一句话内核,简体中文>\",\"embodied\":[\"<KU标题>\"]}.")
    r=await cli.post("https://api.deepseek.com/chat/completions",headers={"Authorization":"Bearer "+KEY},
        json={"model":"deepseek-v4-flash","response_format":{"type":"json_object"},
              "messages":[{"role":"system","content":SYS},{"role":"user","content":f"Concept: {concept}\n\n{kus_text[:4000]}"}]})
    return json.loads(r.json()["choices"][0]["message"]["content"])
async def go():
    c=await asyncpg.connect(os.getenv('DATABASE_URL'))
    dao=await c.fetch("SELECT title,left(natural_text_zh,260) t FROM aii.ku_onto WHERE substrate_id='advmath_tongji_v1' AND title ~ '导数|微分|可导|求导' LIMIT 8")
    bji=await c.fetch("SELECT title,left(natural_text,260) t FROM aii.ku_onto WHERE substrate_id='microecon_en_full_v2' AND title ~* 'marginal' LIMIT 8")
    await c.close()
    dtext="\n".join(f"[{r['title']}] {r['t']}" for r in dao)
    btext="\n".join(f"[{r['title']}] {r['t']}" for r in bji)
    async with httpx.AsyncClient(trust_env=False,timeout=60) as cli:
        e_dao=await essence(cli,"导数(derivative)",dtext)
        e_bji=await essence(cli,"边际(marginal)",btext)
        print("【导数 本性】", e_dao.get('core'))
        print("  溯源:", e_dao.get('embodied',[])[:4])
        print("【边际 本性】", e_bji.get('core'))
        print("  溯源:", e_bji.get('embodied',[])[:4])
        # ★判本性同一(守命门)
        JSYS=("Judge whether two concepts from DIFFERENT disciplines share the SAME invariant core (本性同一). "
              "★STRICT: assert sameness ONLY if their cores are genuinely the SAME underlying invariant "
              "(not just topically related, not 附会硬凑). If not clearly same, say verdict='not_same' and explain. "
              'Output JSON {"verdict":"same|not_same","shared_invariant":"<若same,共同不变量,简体>","why":"<理由,简体>"}.')
        r=await cli.post("https://api.deepseek.com/chat/completions",headers={"Authorization":"Bearer "+KEY},
            json={"model":"deepseek-v4-flash","response_format":{"type":"json_object"},
                  "messages":[{"role":"system","content":JSYS},{"role":"user","content":f"导数(数学)本性: {e_dao.get('core')}\n边际(经济)本性: {e_bji.get('core')}"}]})
        j=json.loads(r.json()["choices"][0]["message"]["content"])
        print(f"\n★本性同一判定: {j.get('verdict')}")
        print(f"  共同不变量: {j.get('shared_invariant')}")
        print(f"  理由: {j.get('why')}")
asyncio.run(go())
