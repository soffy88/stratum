import logging
import re
from typing import Any
import numpy as np

from oskill.ku_extract_pipeline import ku_extract_pipeline
from omodul.register_ku import register_ku, RegisterKuConfig
from omodul.knowledge_reflux import run_reflux, KnowledgeRefluxConfig
from oprim import vector_encode

from aii.storage.pg_backend import PgBackend

logger = logging.getLogger(__name__)

class KuIngestionEngine:
    """End-to-end Knowledge Unit Ingestion Engine."""

    def __init__(self, backend: PgBackend):
        self.backend = backend

    _GRADE_RANKS: dict[str, int] = {
        "unverified": 0, "low": 1, "medium": 2,
        "high": 3, "verified": 4, "proven": 5,
    }

    async def ingest(
        self,
        text: str,
        project_id: str = "default",
        substrate_id: str = "",
        grade_cap: str | None = None,
        provider: str = "default",
    ) -> dict[str, Any]:
        """Process raw text into knowledge units and store them."""
        # Strip picture-omitted placeholders from PDF markdown before extraction
        text = re.sub(
            r'[^\n]*(?:picture|figure|image)[^\n]*(?:intentionally\s+)?omitted[^\n]*\n?',
            '', text, flags=re.IGNORECASE
        )
        text = text.strip()

        # 1. Extraction Pipeline (oskill)
        logger.info(f"Extracting KUs from text (length: {len(text)}) provider={provider}")
        extracted = ku_extract_pipeline(
            text=text,
            project_id=project_id,
            provider=provider,
        )

        candidates = extracted.get("candidates", [])
        rejected = extracted.get("rejected", [])

        results = {
            "registered": [],
            "quarantined": [],
            "chunks_processed": extracted.get("chunks_processed", 0)
        }

        # Apply substrate_id + grade_cap before registration
        cap_rank = self._GRADE_RANKS.get(grade_cap, 999) if grade_cap else 999
        for cand in candidates:
            if substrate_id:
                cand["substrate_id"] = substrate_id
            if grade_cap:
                g = cand.get("grade", "unverified")
                if self._GRADE_RANKS.get(g, 0) > cap_rank:
                    cand["grade"] = grade_cap

        # 2. Register Candidates (omodul)
        config = RegisterKuConfig(backend=self.backend)

        for cand in candidates:
            # 策略B: 向量化输入用 「名称:natural_text」
            name = cand.get("name") or cand.get("title", "unnamed")
            natural_text = cand.get("natural_text", "")
            embed_input = f"{name}:{natural_text}"

            logger.info(f"Encoding vector for KU: {name}")
            embedding = vector_encode(texts=[embed_input], provider="default")
            cand["embedding"] = embedding[0].tolist() if isinstance(embedding, np.ndarray) else embedding[0]

            # Register via omodul
            try:
                reg_res = register_ku(config, {"ku": cand})
                results["registered"].append(cand.get("ku_id"))
            except Exception as e:
                logger.error(f"Failed to register KU {name}: {e}")

        # 3. Handle Rejected (Quarantine)
        for rej in rejected:
            ku_id = rej.get("ku_id")
            if ku_id:
                await self.backend.quarantine_ku(ku_id, reason="extraction_rejected")
                results["quarantined"].append(ku_id)

        # 4. Trigger Reflux (omodul)
        logger.info("Triggering knowledge reflux for graph completion")
        reflux_config = KnowledgeRefluxConfig(backend=self.backend)
        try:
            run_reflux(reflux_config, {})
        except Exception as e:
            logger.warning(f"Knowledge reflux failed: {e}")

        return results
