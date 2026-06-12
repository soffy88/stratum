import logging
from typing import Any

from omodul.knowledge_reflux import run_reflux, KnowledgeRefluxConfig
from omodul.verify_knowledge import verify_knowledge, VerifyKnowledgeConfig
from omodul.learning_distill import learning_distill, LearningDistillConfig
from omodul.governance_adjudicate import governance_adjudicate, GovernanceAdjudicateConfig

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
            "needs_review": []
        }

        # =====================================================================
        # Step 1: Graph Completion & Coherence (Reflux)
        # =====================================================================
        logger.info("Step 1: Graph Reflux")
        reflux_config = KnowledgeRefluxConfig(
            backend=self.backend, 
            auto_apply_low=True # Auto-apply coherence_boost and missing_inverse
        )
        try:
            reflux_result = run_reflux(reflux_config, {})
            # Extract findings. Ensure it's a list.
            findings = reflux_result.get("findings") or []
            for f in findings:
                if f.get("kind") in ["missing_inverse", "coherence_boost"] and f.get("applied"):
                     report["reflux_applied"].append(f)
                else:
                    # High risk (contradiction, defeater, supersede_stale) go to review
                    report["needs_review"].append(f)
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
        
        vk_config = VerifyKnowledgeConfig()

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
                logger.debug(f"Verifying theorem: {name}")
                res = await self.formal_proof_engine.verify(ku)
                if res["status"] == "proven":
                    report["upgraded"].append(ku_id)
                elif res["status"] == "not_elevated":
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
                    vk_result = verify_knowledge(vk_config, v_input)
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
        distill_config = LearningDistillConfig()
        # In a real run, we fetch recent episodes to distill into solution_strategies.
        # For this skeleton, we run it with an empty payload to test orchestration.
        try:
             # Input expects episodes with success/failure signals
             distill_res = learning_distill(distill_config, {"episodes": []})
             # report["distilled"] = len(distill_res.get("findings", {}).get("strategies_generated", []))
             report["distilled"] = 0 
        except Exception as e:
             logger.error(f"Distillation failed: {e}")

        # =====================================================================
        # Step 4: Governance Adjudication (Human-in-the-loop preparation)
        # =====================================================================
        logger.info("Step 4: Governance Adjudication")
        gov_config = GovernanceAdjudicateConfig(backend=self.backend)
        # We pass the high-risk items collected during reflux into governance
        gov_input = {
            "pending_decisions": report["needs_review"]
        }
        try:
            gov_res = governance_adjudicate(gov_config, gov_input)
            # Governance processes them and might mark them for human review
            # We don't automatically apply high-risk changes here.
        except Exception as e:
             logger.error(f"Governance failed: {e}")

        logger.info("Evolution Cycle Complete.")
        return report
