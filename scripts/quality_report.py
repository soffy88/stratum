"""单本飞轮质量自检报告: 跑完出报告 + 报警阈值 → 人工确认才入正式库.
Usage: quality_report.py <substrate_id>  (默认 microecon_en_full_v2)"""
import asyncio, asyncpg, os, re, sys, json
from pathlib import Path
from dotenv import load_dotenv
ROOT=Path(__file__).resolve().parents[1]; load_dotenv(ROOT/"aii"/".env", override=True)
sys.path.insert(0,str(ROOT/"scripts"))
SUB=sys.argv[1] if len(sys.argv)>1 else "microecon_en_full_v2"
# 报警阈值(规范)
TH={"complete":100,"residual_max":0,"shell_max":0,"bilingual_min":99,"directed_min":150}
async def go():
    c=await asyncpg.connect(os.getenv('DATABASE_URL'))
    R={}; alarms=[]
    R['KU总数']=await c.fetchval(f"SELECT count(*) FROM aii.ku_onto WHERE substrate_id='{SUB}'")
    R['双语率%']=round(100*(await c.fetchval(f"SELECT count(*) FILTER(WHERE natural_text_zh ~ '[一-龥]') FROM aii.ku_onto WHERE substrate_id='{SUB}'"))/max(R['KU总数'],1))
    R['残留字符KU']=await c.fetchval(r"SELECT count(*) FROM aii.ku_onto WHERE substrate_id=$1 AND natural_text_zh ~ '##|\*\*|未涉及|\[Ch|經|濟'", SUB)
    # 空壳(中文<10字)
    R['空壳KU']=await c.fetchval(f"SELECT count(*) FROM aii.ku_onto WHERE substrate_id='{SUB}' AND length(regexp_replace(natural_text_zh,'[^一-龥]','','g'))<10")
    # 有向边
    R['有向边']=await c.fetchval(f"SELECT count(*) FROM aii.directed_edge_v2 WHERE substrate_id='{SUB}'") or 0
    R['章节KC']=await c.fetchval(f"SELECT count(*) FROM aii.kc_onto WHERE substrate_id='{SUB}' AND synthesis_marker='AII章节KC'") or 0
    R['BU入库']='是' if await c.fetchval(f"SELECT count(*) FROM aii.bu_onto WHERE substrate_id='{SUB}'") else '否'
    # 完整性(重算: 各章应有黑体术语 vs 抽出)
    try:
        from chapter_ingest import slice_chapter, SM, chapter_numbers
        from aii.service.planning_completeness import check_completeness
        full=SM.read_text(encoding='utf-8',errors='replace')
        chs=chapter_numbers(full)  # 英文 # Chapter 或中文 第N章 自动
        incomplete=[]
        for ch in chs:
            names=[r['title'] for r in await c.fetch(f"SELECT title FROM aii.ku_onto WHERE substrate_id='{SUB}' AND (provenance->>'chapter')::int=$1",ch)]
            comp=check_completeness(slice_chapter(full,ch),names)
            if not comp['complete']: incomplete.append((ch,comp['missing_bold_terms']))
        R['完整章%']=round(100*(len(chs)-len(incomplete))/max(len(chs),1))
        R['漏知识点章']=incomplete[:3]
    except Exception as e:
        R['完整章%']=f'(算不了:{str(e)[:30]})'
    # 报警
    if isinstance(R['完整章%'],int) and R['完整章%']<TH['complete']: alarms.append(f"完整率{R['完整章%']}%<100")
    if R['残留字符KU']>TH['residual_max']: alarms.append(f"残留字符{R['残留字符KU']}>0")
    if R['空壳KU']>TH['shell_max']: alarms.append(f"空壳{R['空壳KU']}>0")
    if R['双语率%']<TH['bilingual_min']: alarms.append(f"双语{R['双语率%']}%<99")
    if R['有向边']<TH['directed_min']: alarms.append(f"有向边{R['有向边']}<150")
    print(f"\n{'='*50}\n质量自检报告: {SUB}\n{'='*50}")
    for k,v in R.items(): print(f"  {k}: {v}")
    print(f"\n报警({len(alarms)}): {alarms if alarms else '✅ 全部达标, 可人工确认入正式库'}")
    print("注: KU忠实/有向精度/BU脑补 需LLM抽检(异源), 见 deterministic 上方; 这三项建议人工抽样确认.")
    await c.close()
asyncio.run(go())
