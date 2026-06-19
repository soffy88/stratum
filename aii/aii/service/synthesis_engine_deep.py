"""DeepSynthesisEngine — 社区聚类 + 大局摘要 + 书级理解 (K-AII-4 / M-AII-3 / M-AII-4).

命门:
  - LLM综合KU的 is_synthesis=True, synthesis_note='AII综合，非原文断言' (omodul强制)
  - grade ≤ max(源KU grade), 上限 high (summary_synthesize 内部强制)
  - 书级论断带 stance_marker, argument_structure 论据grade独立
  - 综合KU写入时标 is_synthesis=True + synthesis_meta

接口约定 (来自实测):
  summary_synthesize 返回平铺 dict:
    status, summary_text, grade, is_synthesis, synthesis_note, source_ku_ids …
  book_understanding_synthesize 返回平铺 dict:
    status, summary, is_synthesis, synthesis_note,
    main_claims, argument_structure, key_concept_ku_ids, structure …
"""
from __future__ import annotations

import asyncio
import logging
import tempfile
import uuid
from pathlib import Path
from typing import Any

from oprim._aii_graph_types import SummarySynthesizeInput, BookUnderstandingInput
from oskill import community_cluster
from omodul.summary_synthesize import SummarySynthesizeConfig, summary_synthesize
from omodul.book_understanding_synthesize import BookUnderstandingConfig, book_understanding_synthesize

from obase import ProviderRegistry

from aii.storage.pg_backend import PgBackend

logger = logging.getLogger(__name__)


def _embed(text: str) -> list[float] | None:
    """Embed a single text using the registered embedding provider."""
    try:
        reg = ProviderRegistry.get()
        embed_fn = reg._generic.get("embedding", {}).get("default")
        if embed_fn is None:
            return None
        import numpy as np
        vecs = embed_fn([text])
        arr = np.array(vecs, dtype="float32")
        norm = float(np.linalg.norm(arr[0]))
        return [float(x) / norm for x in arr[0]] if norm > 0 else [float(x) for x in arr[0]]
    except Exception as e:
        logger.warning("embed failed: %s", e)
        return None


class DeepSynthesisEngine:
    """Orchestrates community clustering, summary synthesis, and book understanding."""

    def __init__(self, backend: PgBackend):
        self.backend = backend

    # ──────────────────────────────────────────────────────────────────────
    # Public entry points
    # ──────────────────────────────────────────────────────────────────────

    def build_overview(self, ku_ids: list[str]) -> dict[str, Any]:
        """同步入口: 社区聚类 → 每社区大局摘要 KU."""
        try:
            asyncio.get_running_loop()
            import concurrent.futures as _cf
            with _cf.ThreadPoolExecutor(max_workers=1) as ex:
                return ex.submit(asyncio.run, self._build_overview_async(ku_ids)).result()
        except RuntimeError:
            return asyncio.run(self._build_overview_async(ku_ids))

    async def build_overview_async(self, ku_ids: list[str], provider: str = "default") -> dict[str, Any]:
        return await self._build_overview_async(ku_ids, provider=provider)

    async def build_book_understanding_async(
        self,
        book_substrate_id: str,
        ku_ids: list[str],
        doc_type: str = "science",
        provider: str = "default",
    ) -> dict[str, Any]:
        return await self._build_book_understanding_async(book_substrate_id, ku_ids, doc_type, provider=provider)

    # ──────────────────────────────────────────────────────────────────────
    # Step A: Community cluster + summary synthesis
    # ──────────────────────────────────────────────────────────────────────

    async def _build_overview_async(self, ku_ids: list[str], provider: str = "default") -> dict[str, Any]:
        # 1. 取 embedding 向量
        embeddings_map = await self.backend.get_ku_embeddings(ku_ids)
        kus_with_emb = [(kid, embeddings_map[kid]) for kid in ku_ids if kid in embeddings_map]

        if not kus_with_emb:
            logger.warning("No embeddings found for any KU; cannot cluster")
            return {"communities": 0, "synthesis_kus": [], "error": "no_embeddings"}

        emb_ids = [x[0] for x in kus_with_emb]
        emb_vecs = [x[1] for x in kus_with_emb]

        # 2. 社区聚类
        logger.info("community_cluster: %d KUs", len(emb_ids))
        try:
            communities = community_cluster(
                ku_ids=emb_ids,
                embeddings=emb_vecs,
                min_community_size=2,  # 5个KU时用2, 正式书摄入用3
            )
        except Exception as e:
            logger.error("community_cluster failed: %s", e)
            return {"communities": 0, "synthesis_kus": [], "error": str(e)}

        logger.info("Got %d communities", len(communities))

        # 3. 加载 KU 完整数据
        all_kus = await self.backend.list_kus()
        ku_data: dict[str, dict] = {str(ku["ku_id"]): ku for ku in all_kus}

        synthesis_ku_ids = []
        with tempfile.TemporaryDirectory(prefix="aii_synthesis_") as tmp:
            tmp_path = Path(tmp)

            for comm in communities:
                comm_ku_ids = [kid for kid in comm.ku_ids if kid in ku_data]
                if not comm_ku_ids:
                    continue

                ku_texts = [str(ku_data[kid].get("natural_text") or "") for kid in comm_ku_ids]
                source_grades = [str(ku_data[kid].get("grade") or "unverified") for kid in comm_ku_ids]

                config = SummarySynthesizeConfig(
                    community_label=comm.label,
                    max_source_kus=20,
                    llm_provider=provider,
                )
                input_data = SummarySynthesizeInput(
                    ku_ids=comm_ku_ids,
                    ku_texts=ku_texts,
                    source_grades=source_grades,
                )

                logger.info("summary_synthesize: community=%s n=%d", comm.label[:20], len(comm_ku_ids))
                try:
                    result = await summary_synthesize(config, input_data, tmp_path)
                except Exception as e:
                    logger.error("summary_synthesize failed for community %s: %s", comm.label, e)
                    continue

                if result.get("status") != "completed":
                    logger.warning("summary_synthesize status=%s for %s", result.get("status"), comm.label)
                    continue

                # summary_synthesize 返回平铺 dict (实测确认)
                syn_text = result.get("summary_text") or ""
                if not syn_text:
                    continue
                syn_grade = result.get("grade", "unverified")

                embedding = _embed(syn_text)

                syn_ku_id = str(uuid.uuid4())
                await self.backend._put_ku_async({
                    "ku_id": syn_ku_id,
                    "natural_text": syn_text,
                    "knowledge_type": "synthesis",
                    "grade": syn_grade,
                    "source": "aii_synthesis",
                    "embedding": embedding,
                    "is_synthesis": True,
                    "synthesis_meta": {
                        "synthesis_note": result.get("synthesis_note", "AII综合，非原文断言"),
                        "community_label": comm.label,
                        "source_ku_ids": result.get("source_ku_ids", comm_ku_ids),
                        "community_size": comm.size,
                    },
                })
                synthesis_ku_ids.append(syn_ku_id)
                logger.info("Stored synthesis KU %s grade=%s for community %s",
                            syn_ku_id[:8], syn_grade, comm.label)

        return {
            "communities": len(communities),
            "synthesis_kus": synthesis_ku_ids,
            "synthesis_count": len(synthesis_ku_ids),
        }

    # ──────────────────────────────────────────────────────────────────────
    # Step B: Book-level understanding synthesis
    # ──────────────────────────────────────────────────────────────────────

    async def _build_book_understanding_async(
        self,
        book_substrate_id: str,
        ku_ids: list[str],
        doc_type: str = "science",
        provider: str = "default",
    ) -> dict[str, Any]:
        # 加载 KU 数据
        all_kus = await self.backend.list_kus()
        ku_data: dict[str, dict] = {str(ku["ku_id"]): ku for ku in all_kus}

        valid_ids = [kid for kid in ku_ids if kid in ku_data]
        if not valid_ids:
            return {"status": "failed", "error": "no_valid_kus"}

        ku_texts = [str(ku_data[kid].get("natural_text") or "") for kid in valid_ids]
        ku_grades = [str(ku_data[kid].get("grade") or "unverified") for kid in valid_ids]

        config = BookUnderstandingConfig(
            book_substrate_id=book_substrate_id,
            doc_type=doc_type,
            llm_provider=provider,
        )
        input_data = BookUnderstandingInput(
            ku_ids=valid_ids,
            ku_texts=ku_texts,
            ku_grades=ku_grades,
        )

        with tempfile.TemporaryDirectory(prefix="aii_book_") as tmp:
            tmp_path = Path(tmp)
            logger.info("book_understanding_synthesize: substrate=%s doc_type=%s n=%d",
                        book_substrate_id, doc_type, len(valid_ids))
            try:
                result = await book_understanding_synthesize(config, input_data, tmp_path)
            except Exception as e:
                logger.error("book_understanding_synthesize failed: %s", e)
                return {"status": "failed", "error": str(e)}

        if result.get("status") != "completed":
            return {"status": result.get("status"), "error": result.get("error")}

        # book_understanding_synthesize 返回平铺 dict (实测确认)
        summary_text = result.get("summary") or ""
        if not summary_text:
            return {"status": "failed", "error": "empty_summary"}

        embedding = _embed(summary_text)

        book_ku_id = str(uuid.uuid4())
        await self.backend._put_ku_async({
            "ku_id": book_ku_id,
            "natural_text": summary_text,
            "knowledge_type": "book_understanding",
            "grade": "unverified",  # 书级论断保守评级
            "source": "aii_book_understanding",
            "embedding": embedding,
            "is_synthesis": True,
            "synthesis_meta": {
                "synthesis_note": result.get("synthesis_note", "AII综合，非原文断言"),
                "book_substrate_id": book_substrate_id,
                "doc_type": doc_type,
                "main_claims": result.get("main_claims", []),
                "argument_structure": result.get("argument_structure", []),
                "key_concept_ku_ids": result.get("key_concept_ku_ids", []),
                "structure": result.get("structure", ""),
            },
        })

        main_claims = result.get("main_claims", [])
        arg_struct = result.get("argument_structure", [])
        logger.info("Stored book KU %s grade=unverified doc_type=%s claims=%d",
                    book_ku_id[:8], doc_type, len(main_claims))

        return {
            "status": "completed",
            "book_ku_id": book_ku_id,
            "doc_type": doc_type,
            "main_claims_count": len(main_claims),
            "argument_structure_count": len(arg_struct),
        }
