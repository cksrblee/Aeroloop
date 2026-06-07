import uuid
from typing import Any, Dict
from aeroloop.agents.base_agent import BaseAIAgent
from aeroloop.schemas.compliance import CertificationValidationInput, CertificationValidationResult

class CertificationValidatorAgent(BaseAIAgent):
    """
    Evaluates the SizingDraft (ConceptBaseline) against the Certification Compliance Checklist (CCL).
    This agent is deterministic and uses rule-based logic to verify safety margins and limits.
    """
    def __init__(self, **kwargs):
        super().__init__(
            name="Certification Validator Agent",
            description="Verifies the reasoned Concept Baseline against the certification compliance checklist.",
            **kwargs
        )
        
    def validate(self, request: CertificationValidationInput) -> CertificationValidationResult:
        baseline = request.concept_baseline
        ccl_items = request.compliance_result.ccl_items
        
        violations = []
        warnings = []
        
        # Example validation logic based on SC-VTOL / Industry Standards
        if baseline.battery_reserve_percent_target is not None:
            if baseline.battery_reserve_percent_target < 20.0:
                violations.append(f"Battery reserve target ({baseline.battery_reserve_percent_target}%) is below the minimum required SC-VTOL margin of 20%.")
        else:
            warnings.append("Battery reserve target was not specified in the concept baseline. Defaulting to high risk.")
            
        if baseline.target_payload_kg is not None and baseline.target_payload_kg > 5000:
            warnings.append(f"Payload ({baseline.target_payload_kg} kg) exceeds typical small VTOL limits, might trigger higher certification category.")
            
        # Additional checks can be implemented by iterating over ccl_items
        for item in ccl_items:
            if "noise" in item.topic_area.lower() and baseline.noise_level_target_db is not None:
                if baseline.noise_level_target_db > 75.0:
                    warnings.append(f"Noise level target ({baseline.noise_level_target_db} dB) may exceed strict urban operation rules.")
        
        is_valid = len(violations) == 0
        
        return CertificationValidationResult(
            validation_id=f"VAL-{uuid.uuid4().hex[:8]}",
            run_id=request.run_id,
            is_valid=is_valid,
            violations=violations,
            warnings=warnings,
            status="success" if is_valid else "failed"
        )
        
    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        req_dict = state.get("certification_validation_input")
        if not req_dict:
            return state
            
        if isinstance(req_dict, dict):
            req = CertificationValidationInput(**req_dict)
        else:
            req = req_dict
            
        result = self.validate(req)
        state["certification_validation_result"] = result
        return state
