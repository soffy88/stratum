import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

import omodul.knowledge_reflux
import omodul.verify_knowledge
import omodul.learning_distill
import omodul.governance_adjudicate
from oprim import failure_lesson_extract
from oskill import capability_gap_analyze

from aii.storage.pg_backend import PgBackend
from aii.service.formal_proof_engine import FormalProofEngine

logger = logging.getLogger(__name__)

class EvolutionEngine:
    """Orchestrates the self-evolution flywheel for the AII system."""

    def __init__(self, backend: PgBackend):
        self.backend = backend
        self.formal_proof_engine = FormalProofEngine(backend=backend)

    async def evolve(self) -> dict[str, Any]:
        """Run a single iteration of the evolution cycle.
        
        Orchestrates 4 steps: Reflux -> Verify -> Distill -> Govern.
        Adheres strictly to H1-modul (services orchestrate omoduls, no omodul internal calling).
        """
        logger.info("Starting Evolution Cycle...")
        report = {
            "reflux_applied": [],
            "upgraded": [],
            "downgraded": [],
            "capped": [],
            "skipped": [],
            "distilled": 0,
            "needs_review": [],
            "gaps": None,
        }

        loop = asyncio.get_event_loop()

        # =====================================================================
        # Step 1: Graph Completion & Coherence (Reflux)
        # =====================================================================
        logger.info("Step 1: Graph Reflux")
        reflux_config = omodul.knowledge_reflux.KnowledgeRefluxConfig(
            backend=self.backend,
            auto_apply_low=True # Auto-apply coherence_boost and missing_inverse
        )
        try:
            reflux_result = await loop.run_in_executor(
                None, lambda: omodul.knowledge_reflux.run_reflux(reflux_config, {})
            )
            # findings is a RefluxReport dataclass object, not a dict or list
            reflux_report = reflux_result.get("findings")
            if reflux_report is not None:
                # auto_applied: low-risk items already executed by run_reflux
                for f in reflux_report.auto_applied:
                    report["reflux_applied"].append({
                        "kind": f.kind, "subject": f.subject,
                        "severity": f.severity, "detail": f.detail,
                    })
                # needs_review: high-risk items for governance/human-in-the-loop
                for f in reflux_report.needs_review:
                    item = {
                        "kind": f.kind, "subject": f.subject,
                        "severity": f.severity, "detail": f.detail,
                    }
                    report["needs_review"].append(item)
                    # coherence_defeater: record failure lesson (bypass, don't change grade)
                    if f.kind == "coherence_defeater":
                        try:
                            contradictors = f.detail.get("contradictors", [])
                            fl = failure_lesson_extract(
                                trigger_type="defeater_struck",
                                evidence={"contradicts_from": str(contradictors)},
                                subject_ref=str(f.subject),
                            )
                            await self.backend.record_failure_lesson_async(
                                fl.trigger_type, fl.subject_ref, fl.evidence, fl.lesson
                            )
                        except Exception as e:
                            logger.warning(f"Defeater lesson extract failed: {e}")
        except Exception as e:
            logger.error(f"Reflux failed: {e}")

        # =====================================================================
        # Step 2: Evidence-Based Verification
        # =====================================================================
        logger.info("Step 2: Verification")
        # Fetch KUs that might need verification (unverified, low, moderate, high)
        pool = await self.backend._ensure_pool()
        async with pool.acquire() as conn:
            # We don't fetch proven or quarantined
            candidate_rows = await conn.fetch(
                "SELECT * FROM aii.ku WHERE grade != 'proven' AND is_quarantined = FALSE"
            )
        
        vk_config = omodul.verify_knowledge.VerifyKnowledgeConfig()

        import json
        for row in candidate_rows:
            ku = dict(row)
            
            # Parse JSON fields if they are returned as strings by asyncpg
            for json_field in ["symbolic_form", "provenance"]:
                if ku.get(json_field) and isinstance(ku[json_field], str):
                    try:
                        ku[json_field] = json.loads(ku[json_field])
                    except json.JSONDecodeError:
                        pass

            ku_id = str(ku["ku_id"])
            k_type = ku.get("knowledge_type")
            name = ku.get("natural_text", "")[:10] # snippet for logging
            
            # 2a. Mathematical Theorems -> FormalProofEngine
            if k_type == "theorem":
                # 确证前查重蹈：已知失败则跳过，省成本
                theorem_name = (
                    ku.get("symbolic_form", {}).get("name", "") if isinstance(ku.get("symbolic_form"), dict) else ""
                ) or ku.get("name", "") or ku.get("natural_text", "")[:30]
                if theorem_name and await self.backend.has_failure_lesson_async("verify_failed", theorem_name):
                    logger.info(f"Skipping known failure theorem: {theorem_name}")
                    report["skipped"].append(ku_id)
                    continue
                logger.debug(f"Verifying theorem: {name}")
                res = await self.formal_proof_engine.verify(ku)
                if res["status"] == "proven":
                    report["upgraded"].append(ku_id)
                elif res["status"] == "not_elevated":
                    # 记失败教训（loogle_count=0，旁路不改grade）
                    try:
                        fl = failure_lesson_extract(
                            trigger_type="verify_failed",
                            evidence={"loogle_count": 0},
                            subject_ref=theorem_name or ku_id,
                        )
                        await self.backend.record_failure_lesson_async(
                            fl.trigger_type, fl.subject_ref, fl.evidence, fl.lesson
                        )
                    except Exception as e:
                        logger.warning(f"Failure lesson extract failed: {e}")
                    report["skipped"].append(ku_id)
                continue

            # 2b. Empirical Knowledge -> verify_knowledge (Requires Evidence)
            provenance = ku.get("provenance", {})
            if not provenance:
                # No evidence -> Do not self-deceive. Skip.
                report["skipped"].append(ku_id)
                continue

            v_type = None
            v_input = {"ku": ku}
            
            # Check for CMI or Backtest evidence
            if "cmi_treatment" in provenance and "cmi_control" in provenance:
                v_type = "cmi"
                v_input.update({
                    "type": "cmi",
                    "treatment": provenance["cmi_treatment"],
                    "control": provenance["cmi_control"]
                })
            elif "backtest_returns" in provenance:
                v_type = "backtest"
                v_input.update({
                    "type": "backtest",
                    "returns": provenance["backtest_returns"]
                })
            
            if v_type:
                logger.debug(f"Verifying empirical KU ({v_type}): {name}")
                try:
                    vk_result = await loop.run_in_executor(
                        None, lambda vi=v_input: omodul.verify_knowledge.verify_knowledge(vk_config, vi)
                    )
                    vk_findings = vk_result.get("findings")
                    
                    if vk_findings:
                        action = vk_findings.get("action")
                        if action == "upgraded":
                            report["upgraded"].append(ku_id)
                        elif action == "downgraded":
                            report["downgraded"].append(ku_id)
                        elif action == "capped":
                            report["capped"].append(ku_id)
                        
                        # Apply the change atomically
                        if action in ["upgraded", "downgraded"]:
                            await self.backend.record_state_change(
                                ku_id=ku_id,
                                to_grade=vk_findings["new_grade"],
                                reason=f"empirical_verification:{v_type}",
                                decision_trail=vk_result.get("decision_trail", [])
                            )
                except Exception as e:
                    logger.error(f"Empirical verification failed for {ku_id}: {e}")
            else:
                 # Provenance exists but no actionable structural evidence
                 report["skipped"].append(ku_id)

        # =====================================================================
        # Step 3: Skill Distillation
        # =====================================================================
        logger.info("Step 3: Skill Distillation")
        distill_config = omodul.learning_distill.LearningDistillConfig()
        # In a real run, we fetch recent episodes to distill into solution_strategies.
        # For this skeleton, we run it with an empty payload to test orchestration.
        try:
             # Input expects episodes with success/failure signals
             distill_res = await loop.run_in_executor(
                 None, lambda: omodul.learning_distill.learning_distill(distill_config, {"episodes": []})
             )
             # report["distilled"] = len(distill_res.get("findings", {}).get("strategies_generated", []))
             report["distilled"] = 0 
        except Exception as e:
             logger.error(f"Distillation failed: {e}")

        # =====================================================================
        # Step 4: Governance Adjudication (Human-in-the-loop preparation)
        # =====================================================================
        logger.info("Step 4: Governance Adjudication")
        gov_config = omodul.governance_adjudicate.GovernanceAdjudicateConfig(backend=self.backend)
        # We pass the high-risk items collected during reflux into governance
        gov_input = {
            "pending_decisions": report["needs_review"]
        }
        try:
            gov_res = await loop.run_in_executor(
                None, lambda: omodul.governance_adjudicate.governance_adjudicate(gov_config, gov_input)
            )
            # Governance processes them and might mark them for human review
            # We don't automatically apply high-risk changes here.
        except Exception as e:
             logger.error(f"Governance failed: {e}")

        # =====================================================================
        # Step 5: Capability Gap Analysis (纯统计，无LLM，不自动补)
        # =====================================================================
        logger.info("Step 5: Capability Gap Analysis")
        try:
            grade_dist = await self.backend.get_grade_distribution_async()

            # failure_stats: aggregate retrieval_miss by topic
            miss_lessons = await self.backend.query_failure_lessons_async(trigger_type="retrieval_miss")
            failure_stats: dict[str, int] = {}
            for l in miss_lessons:
                topic = l.get("subject_ref") or (l.get("evidence") or {}).get("query", "unknown")
                failure_stats[topic] = failure_stats.get(topic, 0) + int(l.get("occurrences", 1))

            # graph_stats: isolated KUs have degree 0
            isolated_ids = await self.backend.get_isolated_kus_async()
            graph_stats = {ku_id: {"degree": 0} for ku_id in isolated_ids}

            # stale_candidates: build from stale unverified rows
            stale_raw = await self.backend.get_stale_unverified_async(days=7)
            now_utc = datetime.now(timezone.utc)
            stale_candidates = []
            for ku in stale_raw:
                updated_at = ku.get("updated_at")
                if updated_at and hasattr(updated_at, "year"):
                    if updated_at.tzinfo is None:
                        updated_at = updated_at.replace(tzinfo=timezone.utc)
                    days_old = (now_utc - updated_at).days
                else:
                    days_old = 7
                stale_candidates.append({
                    "ku_id": str(ku["ku_id"]),
                    "days_unverified": days_old,
                    "verified": ku.get("verified", False),
                })

            gap_report = capability_gap_analyze(
                grade_distribution=grade_dist,
                failure_stats=failure_stats,
                graph_stats=graph_stats,
                stale_threshold_days=7,
                stale_candidates=stale_candidates,
            )

            gap_dict = {
                "high_miss_topics": gap_report.high_miss_topics,
                "stale_unverified": gap_report.stale_unverified,
                "isolated_kus": gap_report.isolated_kus,
                "grade_imbalance": gap_report.grade_imbalance,
            }
            await self.backend.save_capability_gap_async(gap_dict)

            report["gaps"] = {
                "high_miss_topics": gap_report.high_miss_topics,
                "stale_unverified": len(gap_report.stale_unverified),
                "isolated_kus": len(gap_report.isolated_kus),
                "grade_imbalance": gap_report.grade_imbalance,
            }
        except Exception as e:
            logger.error(f"Capability gap analysis failed: {e}")

        logger.info("Evolution Cycle Complete.")
        return report
