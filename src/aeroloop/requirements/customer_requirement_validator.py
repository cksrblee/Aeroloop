from typing import List
from aeroloop.schemas.requirement import CandidateRequirement

class CustomerRequirementValidator:
    def validate(self, candidates: List[CandidateRequirement]) -> List[str]:
        errors = []

        for req in candidates:
            if not 0 <= req.confidence <= 1:
                errors.append(f"{req.candidate_id}: confidence must be between 0 and 1")

            if req.requirement_type == "hard_constraint":
                if req.variable_name is None:
                    errors.append(f"{req.candidate_id}: hard constraint requires variable_name")
                if req.operator is None:
                    errors.append(f"{req.candidate_id}: hard constraint requires operator")

            if req.threshold is None and req.requirement_type == "hard_constraint":
                errors.append(f"{req.candidate_id}: hard constraint should not have null threshold unless needs clarification")

            if req.source_type == "certification_db":
                errors.append(f"{req.candidate_id}: CustomerRequirementAgent must not generate certification_db requirements")

        return errors
