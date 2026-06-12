import logging
from typing import Any
from oskill.formal_proof_verify import formal_proof_verify
from oprim.mathlib_lookup import mathlib_lookup

from aii.storage.pg_backend import PgBackend

logger = logging.getLogger(__name__)

# Pre-verified mappings of theorem names to Lean Mathlib identifiers
# Only identifiers confirmed to have count == 1 are included here.
NAME_DICT = {
    "罗尔定理": "exists_deriv_eq_zero",
    "柯西中值定理": "exists_ratio_deriv_eq_ratio_slope"
}

class FormalProofEngine:
    """Engine for verifying formal proofs of theorems using Lean Mathlib."""

    def __init__(self, backend: PgBackend):
        self.backend = backend

    async def verify(self, ku: dict[str, Any]) -> dict[str, Any]:
        """Attempt to elevate a theorem KU to 'proven' status.
        
        Args:
            ku: The Knowledge Unit dictionary to verify.
        
        Returns:
            The verification result dict.
        """
        if ku.get("knowledge_type") != "theorem":
            return {"status": "skipped", "reason": "not_a_theorem"}

        name = ""
        # Extract name from symbolic_form if available
        symbolic_form = ku.get("symbolic_form")
        if symbolic_form and isinstance(symbolic_form, dict):
            name = symbolic_form.get("name", "")
        
        # Fallback to name parsed during ingestion
        if not name:
            name = ku.get("name", "")
            
        if not name:
             return {"status": "skipped", "reason": "no_name_found"}

        logger.info(f"Verifying formal proof for theorem: {name}")
        
        try:
            # Delegate to oskill for the actual lookup and logic
            result = formal_proof_verify(
                theorem_name=name,
                name_dict=NAME_DICT,
                mathlib_lookup_fn=mathlib_lookup
            )
            
            # Check the verdict
            if result.verdict == "proven":
                logger.info(f"Theorem '{name}' verified as proven. Updating grade.")
                # Atomic state change via PgBackend
                await self.backend.record_state_change(
                    ku_id=str(ku["ku_id"]),
                    to_grade="proven",
                    reason="established_proof",
                    decision_trail=result.model_dump()
                )
                return {"status": "proven", "evidence": result.evidence}
            else:
                logger.info(f"Theorem '{name}' not elevated. Verdict: {result.verdict}")
                return {"status": "not_elevated", "reason": "lookup_failed"}
                
        except Exception as e:
            logger.error(f"Formal verification failed for '{name}': {e}")
            return {"status": "error", "reason": str(e)}
