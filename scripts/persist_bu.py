import asyncio, asyncpg, os, json, httpx
from pathlib import Path
from dotenv import load_dotenv; load_dotenv("/home/soffy/projects/AII/aii/.env", override=True)
SUB=os.getenv('SUBSTRATE','microecon_en_full_v2'); KEY=os.getenv('DEEPSEEK_API_KEY')
async def go():
    bu=json.loads(Path("/tmp/claude-1000/-home-soffy-projects-AII/bebc9349-7f09-4086-abef-c4c9a94f4c0c/scratchpad/bu.json").read_text())
    bu['boundary']="不涉及宏观经济学（GDP、通胀、失业等总量问题），不涉及金融市场的资产定价，不做复杂的数学证明（以直观逻辑为主）。"
    zh={k:bu[k] for k in ['soul','positioning','question','skeleton','thinking','for_whom','boundary']}
    SYS="Translate each JSON value to concise English. Output JSON same keys, English values only."
    r=httpx.post("https://api.deepseek.com/chat/completions",headers={"Authorization":"Bearer "+KEY},
      json={"model":"deepseek-v4-flash","response_format":{"type":"json_object"},
            "messages":[{"role":"system","content":SYS},{"role":"user","content":json.dumps(zh,ensure_ascii=False)}]},timeout=60)
    en=json.loads(r.json()["choices"][0]["message"]["content"])
    c=await asyncpg.connect(os.getenv('DATABASE_URL'))
    await c.execute("ALTER TABLE aii.bu_onto ADD COLUMN IF NOT EXISTS facets_zh jsonb")
    await c.execute("ALTER TABLE aii.bu_onto ADD COLUMN IF NOT EXISTS facets_en jsonb")
    await c.execute("DELETE FROM aii.bu_onto WHERE substrate_id=$1",SUB)
    nkc=await c.fetchval("SELECT count(*) FROM aii.kc_onto WHERE substrate_id=$1",SUB)
    await c.execute("""INSERT INTO aii.bu_onto(substrate_id,doc_type,overview_oneline,problem_statement,learning_thread,
        facets_zh,facets_en,synthesis_marker) VALUES($1,'textbook',$2,$3,$4,$5,$6,'AII综合-书级理解,非原文断言')""",
        SUB, zh['soul'], zh['question'], zh['thinking'], json.dumps(zh,ensure_ascii=False), json.dumps(en,ensure_ascii=False))
    print(f"BU入库(校验版) + 双语 ✓ (关联 {nkc} KC)")
    print("boundary_zh:", zh['boundary'][:60])
    print("soul_en:", en.get('soul','')[:80])
    await c.close()
asyncio.run(go())
