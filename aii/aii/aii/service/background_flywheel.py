"""background_flywheel — 常驻后台飞轮 (asyncio.create_task, 无新依赖).

配置 (环境变量 / 默认值):
  FLYWHEEL_ENABLED          = true      开关
  FLYWHEEL_MAX_FILES_ROUND  = 10        ★限流: 每轮最多处理 N 个文件
  FLYWHEEL_INTERVAL         = 60        轮间隔(秒)
  FLYWHEEL_EVOLVE_EVERY     = 4         每 N 轮跑一次 evolve+needs

守命门:
  - 单轮任何异常 → log + continue, 绝不 crash
  - CancelledError 立即退出 (lifespan shutdown)
  - evolve() 每 EVOLVE_EVERY 轮跑一次, 失败非致命
  - P2.6 purpose: 只导向主动选源(排序), 不拦手动投递/摄取入库
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

_SHARED_DIR = Path(os.getenv("FLYWHEEL_SHARED_DIR", "/home/soffy/shared/stratum-to-aii"))
_OUTPUT_DIR = Path(os.getenv("FLYWHEEL_OUTPUT_DIR", "/home/soffy/shared/aii-to-stratum"))

FLYWHEEL_ENABLED: bool = os.getenv("FLYWHEEL_ENABLED", "true").lower() not in {"false", "0", "no"}
FLYWHEEL_MAX_FILES_ROUND: int = int(os.getenv("FLYWHEEL_MAX_FILES_ROUND", "10"))
FLYWHEEL_INTERVAL: int = int(os.getenv("FLYWHEEL_INTERVAL", "60"))
FLYWHEEL_EVOLVE_EVERY: int = int(os.getenv("FLYWHEEL_EVOLVE_EVERY", "4"))

# 合集过滤: 超过此大小的文件跳过(MB), 0=不过滤
FLYWHEEL_MAX_FILE_MB: float = float(os.getenv("FLYWHEEL_MAX_FILE_MB", "5"))

# P2.6 purpose目的层选源
# purpose.md 由人工维护, AII不自生成/不自改
_PURPOSE_FILE = Path(__file__).parent.parent.parent / "config" / "purpose.md"
_purpose_text: str | None = None  # 缓存: 每次飞轮启动读一次
_purpose_embedding: list[float] | None = None  # 缓存: 启动后算一次
_purpose_title_scores: dict[str, float] = {}  # sid → score 跨轮缓存

# P2.6+ 主动方向缺口: 基于 config/purpose.md 人工整理的核心领域,量化交易重点展开
# ★命门: AII只声明"需要什么方向的书", 不含获取/下载/找书逻辑(Stratum的事)
_PURPOSE_DIRECTIONS: list[dict] = [
    {
        "direction": "量化交易",
        "keywords": ["量化交易", "算法交易", "高频交易", "做市", "统计套利"],
        "subtopics": [
            "高频交易",
            "做市策略",
            "统计套利",
            "市场微观结构",
            "算法交易",
            "金融时间序列",
            "期权定价",
            "风险管理",
            "组合优化",
            "回测方法",
        ],
        "priority": "high",
        "threshold": 500,
    },
    {
        "direction": "金融工程",
        "keywords": ["金融工程", "衍生品", "期权定价", "利率模型", "固定收益"],
        "subtopics": ["衍生品定价", "利率模型", "信用风险", "固定收益", "随机微积分"],
        "priority": "high",
        "threshold": 500,
    },
    {
        "direction": "机器学习",
        "keywords": ["机器学习", "深度学习", "神经网络", "强化学习"],
        "subtopics": ["深度学习", "强化学习", "图神经网络", "生成模型", "transformer架构"],
        "priority": "high",
        "threshold": 1000,
    },
    {
        "direction": "概率统计",
        "keywords": ["概率论", "统计学", "贝叶斯", "随机过程"],
        "subtopics": ["贝叶斯统计", "随机过程", "时间序列分析", "计量经济学"],
        "priority": "medium",
        "threshold": 800,
    },
    {
        "direction": "最优化",
        "keywords": ["最优化", "凸优化", "线性规划", "整数规划"],
        "subtopics": ["凸优化", "随机优化", "组合优化", "运筹学"],
        "priority": "medium",
        "threshold": 300,
    },
    # ── 2026-07-17 相邻学科全覆盖: 从5个量化向扩到全谱, 让找书飞轮拉"各种书"而非只量化 ──
    {
        "direction": "经济学",
        "keywords": ["微观经济学", "宏观经济学", "博弈论", "产业组织", "行为经济学"],
        "subtopics": [
            "微观经济学",
            "宏观经济学",
            "博弈论",
            "产业组织",
            "行为经济学",
            "发展经济学",
            "国际经济学",
            "公共经济学",
        ],
        "priority": "high",
        "threshold": 800,
    },
    {
        "direction": "计量经济学",
        "keywords": ["计量经济学", "因果推断", "面板数据", "工具变量", "断点回归"],
        "subtopics": ["因果推断", "面板数据", "工具变量", "断点回归", "结构估计"],
        "priority": "medium",
        "threshold": 400,
    },
    {
        "direction": "计算机科学与算法",
        "keywords": ["算法", "数据结构", "计算复杂性", "分布式系统", "数据库"],
        "subtopics": [
            "算法设计",
            "数据结构",
            "计算复杂性",
            "分布式系统",
            "数据库系统",
            "操作系统",
            "编译原理",
        ],
        "priority": "medium",
        "threshold": 500,
    },
    {
        "direction": "纯数学",
        "keywords": ["抽象代数", "拓扑", "微分几何", "数论", "泛函分析"],
        "subtopics": [
            "抽象代数",
            "拓扑学",
            "微分几何",
            "数论",
            "实分析",
            "复分析",
            "泛函分析",
            "范畴论",
        ],
        "priority": "medium",
        "threshold": 500,
    },
    {
        "direction": "应用统计",
        "keywords": ["实验设计", "假设检验", "回归分析", "高维统计", "非参数统计"],
        "subtopics": ["实验设计", "回归分析", "高维统计", "非参数统计", "重抽样方法"],
        "priority": "medium",
        "threshold": 400,
    },
    {
        "direction": "物理学",
        "keywords": ["经典力学", "量子力学", "统计物理", "电动力学", "热力学"],
        "subtopics": ["经典力学", "量子力学", "统计物理", "电动力学", "热力学", "相对论"],
        "priority": "medium",
        "threshold": 400,
    },
    {
        "direction": "信息论与信号处理",
        "keywords": ["信息论", "编码理论", "信号处理", "傅里叶", "小波"],
        "subtopics": ["信息论", "编码理论", "数字信号处理", "傅里叶分析", "小波分析"],
        "priority": "low",
        "threshold": 300,
    },
    {
        "direction": "控制与动力系统",
        "keywords": ["控制论", "动力系统", "最优控制", "混沌", "状态空间"],
        "subtopics": ["最优控制", "动力系统", "混沌理论", "状态空间", "系统辨识"],
        "priority": "low",
        "threshold": 300,
    },
    {
        "direction": "运筹与决策科学",
        "keywords": ["运筹学", "决策论", "排队论", "库存", "网络流"],
        "subtopics": ["运筹学", "决策论", "排队论", "库存管理", "网络流"],
        "priority": "low",
        "threshold": 300,
    },
    {
        "direction": "心理学与认知科学",
        "keywords": ["心理学", "认知科学", "行为决策", "神经科学", "社会心理"],
        "subtopics": ["认知心理学", "社会心理学", "行为决策", "神经科学", "发展心理学"],
        "priority": "medium",
        "threshold": 400,
    },
    {
        "direction": "哲学与逻辑",
        "keywords": ["哲学", "逻辑学", "认识论", "伦理学", "科学哲学"],
        "subtopics": ["认识论", "逻辑学", "伦理学", "科学哲学", "形而上学", "心灵哲学"],
        "priority": "low",
        "threshold": 300,
    },
    {
        "direction": "复杂系统与网络科学",
        "keywords": ["复杂系统", "网络科学", "复杂网络", "涌现", "自组织"],
        "subtopics": ["复杂网络", "自组织", "涌现", "系统动力学", "多主体建模"],
        "priority": "low",
        "threshold": 250,
    },
    {
        "direction": "会计与公司金融",
        "keywords": ["公司金融", "会计", "估值", "资本结构", "财务报表"],
        "subtopics": ["公司金融", "财务会计", "估值", "资本结构", "并购"],
        "priority": "medium",
        "threshold": 400,
    },
    {
        "direction": "科学史与科普",
        "keywords": ["科学史", "科普", "科学方法", "科学思想", "科学传记"],
        "subtopics": ["科学史", "科学方法论", "重大科学思想", "科学传记"],
        "priority": "low",
        "threshold": 200,
    },
]


def _read_purpose_text() -> str:
    """Read purpose.md (human-authored direction). Returns "" if missing."""
    if _PURPOSE_FILE.exists():
        return _PURPOSE_FILE.read_text(encoding="utf-8").strip()
    return ""


def _embed_batch(texts: list[str]) -> list[list[float]]:
    """Embed texts via default provider (sync, run in thread executor)."""
    from oprim import vector_encode
    import numpy as np

    raw = vector_encode(texts=texts, provider="default")
    arr = np.array(raw, dtype="float32")
    norms = np.linalg.norm(arr, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1.0, norms)
    return (arr / norms).tolist()


async def _sort_candidates_by_purpose(
    candidates: list[tuple],
) -> list[tuple]:
    """Sort (md, meta, sid) candidates by purpose_alignment_score descending.

    P2.6 命门: 只排序(导向选源), 不过滤. 所有候选仍可进入摄取.
    失败(purpose缺失/embedding错误) → 返回原序不影响流程.
    """
    global _purpose_text, _purpose_embedding

    # 读/缓存 purpose 文本
    if _purpose_text is None:
        _purpose_text = _read_purpose_text()
    if not _purpose_text:
        return candidates  # 无 purpose 文件 → 不排序

    # 计算/缓存 purpose embedding (一次)
    if _purpose_embedding is None:
        try:
            embs = await asyncio.to_thread(_embed_batch, [_purpose_text])
            _purpose_embedding = embs[0]
        except Exception as e:
            logger.warning("purpose: embedding purpose text failed: %s", e)
            return candidates

    # 找需要打分的新候选
    unscored = [(md, meta, sid) for md, meta, sid in candidates if sid not in _purpose_title_scores]
    if unscored:
        titles = [meta.get("title") or meta.get("name") or md.stem for md, meta, sid in unscored]
        try:
            title_embs = await asyncio.to_thread(_embed_batch, titles)
            from oprim import purpose_alignment_score

            for (md, meta, sid), emb in zip(unscored, title_embs):
                title = meta.get("title") or meta.get("name") or md.stem
                try:
                    score = purpose_alignment_score(
                        purpose_text=_purpose_text,
                        ku_text=title,
                        embedding_purpose=_purpose_embedding,
                        embedding_ku=emb,
                    )
                except Exception:
                    score = 0.0
                _purpose_title_scores[sid] = score
        except Exception as e:
            logger.warning("purpose: batch embedding candidates failed: %s", e)
            return candidates  # embedding失败 → 原序

    scored = sorted(candidates, key=lambda x: _purpose_title_scores.get(x[2], 0.0), reverse=True)
    if scored:
        top = scored[0]
        logger.info(
            "purpose: sorted %d candidates, top=%s score=%.3f",
            len(scored),
            (top[1].get("title") or top[2][:12])[:40],
            _purpose_title_scores.get(top[2], 0.0),
        )
    return scored


# 标题关键词过滤: 含这些词的视为合集/套装,跳过等待 Stratum 拆分
_COLLECTION_KEYWORDS = (
    "套装",
    "合集",
    "全集",
    "丛书",
    "系列",
    "册）",
    "册)",
    "全套",
    "百科全书",
    "百科辞典",
    "百科词典",
)


def _is_collection(md: Path, meta: dict) -> tuple[bool, str]:
    """判断是否为合集/超大文件. 返回 (is_skip, reason)."""
    # 文件大小检查
    if FLYWHEEL_MAX_FILE_MB > 0:
        mb = md.stat().st_size / 1024 / 1024
        if mb > FLYWHEEL_MAX_FILE_MB:
            return True, f"file_too_large({mb:.1f}MB>{FLYWHEEL_MAX_FILE_MB}MB)"
    # 标题关键词检查
    title = meta.get("title") or meta.get("name") or ""
    for kw in _COLLECTION_KEYWORDS:
        if kw in title:
            return True, f"collection_keyword({kw!r} in title)"
    return False, ""


def _write_skipped_collections(skipped: list[dict]) -> None:
    """将跳过的合集写到 aii-to-stratum/skipped_collections.json 供 Stratum 返工."""
    if not skipped:
        return
    try:
        _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        out_path = _OUTPUT_DIR / "skipped_collections.json"
        # 合并已有记录(去重)
        existing: list[dict] = []
        if out_path.exists():
            try:
                existing = json.loads(out_path.read_text(encoding="utf-8"))
            except Exception:
                existing = []
        existing_ids = {e.get("id") for e in existing}
        new_entries = [s for s in skipped if s.get("id") not in existing_ids]
        all_entries = existing + new_entries
        out_path.write_text(
            json.dumps(all_entries, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        if new_entries:
            logger.info(
                "flywheel: skipped_collections.json updated (+%d new, %d total)",
                len(new_entries),
                len(all_entries),
            )
    except Exception:
        logger.exception("flywheel: write skipped_collections failed (non-fatal)")


async def _collect_new_files(backend, limit: int) -> list[Path]:
    """返回至多 limit 个尚未摄入的 .md 文件 (配对 .json 必须存在).
    跳过超大合集(>FLYWHEEL_MAX_FILE_MB 或标题含套装/合集等关键词).
    跳过的文件不标为已摄取, Stratum 拆分后可重新进来."""
    found: list[Path] = []
    skipped_collections: list[dict] = []

    # 文件系统扫描放进线程: WSL2 跨文件系统下 Path.exists() 约 100ms/次,
    # 690 个 .md 文件 → ~49s 同步阻塞事件循环. 扫描结果是 (md, meta, sid) 三元组.
    def _scan_candidates() -> list[tuple]:
        result = []
        for md in sorted(_SHARED_DIR.glob("*.md")):
            jp = md.with_suffix(".json")
            if not jp.exists():
                continue
            try:
                meta = json.loads(jp.read_text(encoding="utf-8"))
                sid = meta.get("id", "")
                if sid:
                    result.append((md, meta, sid))
            except Exception:
                logger.warning("flywheel: bad sidecar %s, skip", jp.name)
        return result

    candidates = await asyncio.to_thread(_scan_candidates)

    # P2.6: 按purpose目的对齐分排序 (命门: 只排序不过滤, 手动投递路径不经此处)
    candidates = await _sort_candidates_by_purpose(candidates)

    for md, meta, sid in candidates:
        if len(found) >= limit:
            break
        try:
            if await backend.is_substrate_ingested(sid):
                continue

            # ── 合集/大文件过滤 ──────────────────────────────────────────
            skip, reason = _is_collection(md, meta)
            if skip:
                mb = md.stat().st_size / 1024 / 1024
                title = (meta.get("title") or meta.get("name") or md.stem)[:80]
                logger.info(
                    "flywheel: SKIP collection %s (%.1fMB) reason=%s",
                    title,
                    mb,
                    reason,
                )
                skipped_collections.append(
                    {
                        "id": sid,
                        "title": title,
                        "file": md.name,
                        "size_mb": round(mb, 1),
                        "reason": reason,
                    }
                )
                continue  # 不加入 found, 不标已摄

            found.append(md)
        except Exception:
            logger.warning("flywheel: error checking %s, skip", md.name)

    # 写合集清单供 Stratum 返工
    _write_skipped_collections(skipped_collections)
    return found


_QMD_CONTAINER = "aii-qmd"


async def _qmd_search_existing_corpus(keywords: list[str], *, limit: int = 5) -> list[dict]:
    """查一个 purpose 方向的关键词在 qmd 已索引语料(325本书原始MD)里有没有命中.

    用途: proactive_gap 发现"某方向 KU 太少"时, 顺手看一眼语料库里是不是其实
    已经有相关书, 只是没抽好/没抽全——给这条本来就在算、但从未被下游消费过的
    信号补一层"要不要先回去补抽现有书, 而不是急着找新书"的线索。

    用 `qmd search`(纯 BM25, 无 LLM 扩写/重排)而非 `qmd query`(混合检索)——
    实测 `qmd query` 在这台机器上(CPU-only, 常年高负载)偶发卡住数十秒甚至
    超时, 而这里只是想要一个粗筛信号, 不需要语义排序的精度, `qmd search`
    稳定在1秒内返回。多关键词逐个查再按 docid 去重, 而不是拼成一个查询串——
    `qmd search` 把整个输入当短语/AND匹配, 拼接后几乎搜不到东西(实测验证过)。

    失败(容器没起来/超时/JSON解析失败)返回空列表, 不抛异常——这是锦上添花的
    信号, 不该因为 qmd 不可用就打断 proactive_gap 本身的计算。
    """
    hits_by_docid: dict[str, dict] = {}
    for kw in keywords[:3]:  # 前3个关键词够用, 不为了齐全把耗时拉长
        try:
            proc = await asyncio.create_subprocess_exec(
                "docker",
                "exec",
                _QMD_CONTAINER,
                "qmd",
                "search",
                kw,
                "--json",
                "-n",
                str(limit),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=15)
        except (FileNotFoundError, TimeoutError, asyncio.TimeoutError):
            continue
        try:
            results = json.loads(stdout.decode("utf-8", errors="replace"))
        except json.JSONDecodeError:
            continue
        for r in results:
            docid = r.get("docid")
            if docid and docid not in hits_by_docid:
                hits_by_docid[docid] = {
                    "file": r.get("file", "").removeprefix("qmd://"),
                    "title": r.get("title"),
                    "score": r.get("score"),
                }
    return sorted(hits_by_docid.values(), key=lambda h: -(h.get("score") or 0))[:limit]


async def _compute_proactive_needs(backend) -> list[dict]:
    """主动方向缺口感知: 按purpose核心领域查KU覆盖度, 返回覆盖不足的方向需求列表.

    ★命门: 只判断"需要什么方向的书", 不含获取/下载/找书逻辑(Stratum的事).
    """
    needs: list[dict] = []
    try:
        pool = await backend._ensure_pool()
        async with pool.acquire() as conn:
            for d in _PURPOSE_DIRECTIONS:
                # 参数化 LIKE 查询, 避免字符串拼接
                params = [f"%{kw}%" for kw in d["keywords"]]
                conditions = " OR ".join(f"natural_text LIKE ${i + 1}" for i in range(len(params)))
                sql = f"SELECT count(*) FROM aii.ku_onto WHERE ({conditions})"
                ku_count: int = (await conn.fetchval(sql, *params)) or 0
                if ku_count < d["threshold"]:
                    existing_hits = await _qmd_search_existing_corpus(d["keywords"])
                    needs.append(
                        {
                            "type": "proactive_direction",
                            "topic": d["direction"],
                            "subtopics": d["subtopics"],
                            "reason": f"purpose核心方向,当前覆盖{ku_count}条KU,需补充",
                            "ku_count": ku_count,
                            "priority": d["priority"],
                            # qmd 检索现有325本书原始语料的粗筛信号——空列表=语料库里
                            # 没搜到相关书, 大概率真需要找新源; 非空=语料库里已经有
                            # 相关书, 优先看是不是该回去补抽/修复现有书, 而不是急着
                            # 找新书(qmd 不可用时也是空列表, 不代表语料库没有)。
                            "existing_corpus_hits": existing_hits,
                        }
                    )
                    logger.info(
                        "proactive_gap: %s → %d KU (threshold=%d) → need written",
                        d["direction"],
                        ku_count,
                        d["threshold"],
                    )
                else:
                    logger.info(
                        "proactive_gap: %s → %d KU (threshold=%d) → covered",
                        d["direction"],
                        ku_count,
                        d["threshold"],
                    )
    except Exception:
        logger.exception("proactive_gap: compute failed (non-fatal)")
    return needs


def _write_needs(gaps: dict, proactive_needs: list[dict] | None = None) -> None:
    try:
        _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        existing_path = _OUTPUT_DIR / "needs.json"

        # ── 读取已有 proactive_direction 条目(持久层) ──────────────────────
        # proactive_needs=None  → 本轮未计算(旧代码路径),保留文件里的主动需求
        # proactive_needs=[...] → 本轮重新计算,以新值为准(含空列表=全覆盖)
        if proactive_needs is None:
            existing_proactive: list[dict] = []
            if existing_path.exists():
                try:
                    old = json.loads(existing_path.read_text(encoding="utf-8"))
                    existing_proactive = [
                        n for n in old.get("needs", []) if n.get("type") == "proactive_direction"
                    ]
                except Exception:
                    pass
            merged_proactive = existing_proactive
        else:
            merged_proactive = proactive_needs

        # ── reactive high_miss ────────────────────────────────────────────
        high_miss = gaps.get("high_miss_topics", [])
        reactive_needs = [
            {
                "topic": t["topic"] if isinstance(t, dict) else str(t),
                "reason": "high_miss",
                "miss_count": t.get("miss_count", 0) if isinstance(t, dict) else 0,
            }
            for t in high_miss
        ]

        # P2.6: 对 reactive needs 按 purpose 对齐分排序 (纯keyword，同步，无需embedding)
        # 方向内缺口排前，指导人工找源时优先补方向内知识
        if reactive_needs and _purpose_text:
            from oprim._purpose_alignment_score import _keyword_overlap

            for n in reactive_needs:
                n["purpose_score"] = round(_keyword_overlap(_purpose_text, n["topic"]), 4)
            reactive_needs.sort(key=lambda n: n["purpose_score"], reverse=True)
            logger.info(
                "purpose: needs sorted by purpose score, top=%s score=%.4f",
                reactive_needs[0]["topic"][:30] if reactive_needs else "",
                reactive_needs[0].get("purpose_score", 0) if reactive_needs else 0,
            )

        # 主动需求排前(高优先级), reactive 跟后
        needs = merged_proactive + reactive_needs
        logger.info(
            "proactive_gap: %d direction needs in needs.json (recomputed=%s)",
            len(merged_proactive),
            proactive_needs is not None,
        )

        payload = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "needs": needs,
        }
        existing_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        logger.info("flywheel: wrote needs.json (%d topics)", len(needs))
    except Exception:
        logger.exception("flywheel: needs.json write failed (non-fatal)")


async def _backfill_deep_one(backend) -> bool:
    """已退役: 旧深度理解回填(RelationEngine/DeepSynthesis→旧表)废弃.
    onto 路径(_run_ontology_path)摄取时已内联做 KC/BU, 无需回填. 恒返回 False."""
    return False

    await backend.mark_deep_understood(substrate_id)
    return True


async def flywheel_loop(backend) -> None:
    """后台飞轮主循环. 由 app.py lifespan asyncio.create_task() 启动."""
    from aii.service.auto_ingest import ingest_one
    from aii.service.evolution_engine import EvolutionEngine

    _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    round_num = 0

    logger.info(
        "flywheel: started (enabled=%s max_files=%d interval=%ds evolve_every=%d)",
        FLYWHEEL_ENABLED,
        FLYWHEEL_MAX_FILES_ROUND,
        FLYWHEEL_INTERVAL,
        FLYWHEEL_EVOLVE_EVERY,
    )

    while True:
        try:
            if not FLYWHEEL_ENABLED:
                await asyncio.sleep(60)
                continue

            round_num += 1
            logger.info("flywheel: round %d begin", round_num)

            # ── A. 扫新文件, ★限流 MAX_FILES_ROUND ─────────────────────────
            new_files = await _collect_new_files(backend, FLYWHEEL_MAX_FILES_ROUND)
            if new_files:
                logger.info("flywheel: ingesting %d file(s) this round", len(new_files))
                for md in new_files:
                    try:
                        n = await ingest_one(md, backend)
                        logger.info("flywheel: %s → %s KUs", md.name, n if n >= 0 else "skip")
                    except Exception:
                        logger.exception("flywheel: ingest_one failed for %s (non-fatal)", md.name)
            else:
                logger.info("flywheel: no new files this round")

            # ── A2. 回填深度理解 (已摄入但无深度理解的, 每轮最多3个) ────────
            for _bi in range(3):
                try:
                    did = await _backfill_deep_one(backend)
                    if did:
                        logger.info(
                            "flywheel: backfill deep understanding done (substrate %d/3)", _bi + 1
                        )
                    else:
                        break  # 没有待回填的了
                except Exception:
                    logger.exception("flywheel: backfill failed (non-fatal)")
                    break

            # ── B. 定期 evolve + 写需求文件 ──────────────────────────────────
            if round_num % FLYWHEEL_EVOLVE_EVERY == 0:
                try:
                    logger.info("flywheel: running evolution (round %d)", round_num)
                    ev = EvolutionEngine(backend)
                    report = await ev.evolve()
                    gaps = report.get("gaps") or {}
                    proactive_needs = await _compute_proactive_needs(backend)
                    _write_needs(gaps, proactive_needs)
                    logger.info(
                        "flywheel: evolve done upgraded=%d gaps=%s proactive_needs=%d",
                        len(report.get("upgraded", [])),
                        {k: v for k, v in gaps.items() if k != "grade_imbalance"},
                        len(proactive_needs),
                    )
                except Exception:
                    logger.exception("flywheel: evolve failed (non-fatal)")

        except asyncio.CancelledError:
            logger.info("flywheel: cancelled, shutting down")
            break
        except Exception:
            logger.exception(
                "flywheel: round %d unhandled error (non-fatal, continuing)", round_num
            )

        await asyncio.sleep(FLYWHEEL_INTERVAL)
