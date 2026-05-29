from typing import Any, Dict
from aeroloop.agents.base_agent import BaseAIAgent
from aeroloop.schemas.compliance import (
    CertificationComplianceInput, 
    CertificationComplianceResult
)

# Internal Deterministic Modules
from aeroloop.certification.basis_selector import CertificationBasisSelector
from aeroloop.certification.clause_retriever import ClauseRetriever
from aeroloop.certification.applicability_assessor import ApplicabilityAssessor
from aeroloop.certification.ccl_builder import ComplianceChecklistBuilder
from aeroloop.certification.moc_mapper import MoCMapper
from aeroloop.certification.certification_risk_assessor import CertificationRiskAssessor
from aeroloop.certification.certification_trace_linker import TraceabilityLinker

class CertificationComplianceAgent(BaseAIAgent):
    """
    CertificationComplianceAgent is responsible for reviewing SC-VTOL Small, Small Rotorcraft,
    and Small Aircraft standards for early UAM/eVTOL designs, generating a preliminary
    Compliance Checklist (CCL) and Means of Compliance (MoC) plan for TC preparation.
    """
    def __init__(self, **kwargs):
        super().__init__(
            name="Certification Compliance Agent",
            description="Generates preliminary certification basis, CCL, and MoC for early aircraft concept design.",
            **kwargs
        )
        
        # Initialize deterministic modules
        self.basis_selector = CertificationBasisSelector()
        self.clause_retriever = ClauseRetriever()
        self.applicability_assessor = ApplicabilityAssessor()
        self.ccl_builder = ComplianceChecklistBuilder()
        self.moc_mapper = MoCMapper()
        self.risk_assessor = CertificationRiskAssessor()
        self.trace_linker = TraceabilityLinker()
        
        # System Prompt
        self.system_prompt = """
You are CertificationComplianceAgent for AeroLoop.

Your task is not to make a final legal certification judgment.
Your task is to generate a preliminary certification basis, compliance checklist, and means-of-compliance plan for early aircraft concept design.

You must check exactly three source families:
1. SC_VTOL_SMALL
2. SMALL_ROTORCRAFT
3. SMALL_AIRCRAFT

Use only the provided Certification DB clauses.
Do not invent regulation numbers, clause numbers, or compliance requirements.
If a clause is not found in the DB, mark it as unresolved instead of fabricating it.

For each relevant clause:
- Determine applicability status: included, excluded, not_applicable, tbd, or requires_human_review.
- Explain why it applies or does not apply.
- Link it to mission fields or customer requirements.
- Create a Compliance Checklist Item.
- Propose Means of Compliance methods such as design_review, engineering_analysis, simulation, ground_test, flight_test, software_verification, safety_assessment, similarity, or expert_review.
- Clearly distinguish preliminary PoC support from real certification evidence.

Special rule:
If design information is insufficient, do not exclude the item. Mark it as tbd or requires_human_review.

Return only valid JSON matching the CertificationComplianceResult schema.
        """.strip()

    # @observe(name="certification-compliance-analysis") # Langfuse decorator example
    def analyze(self, input_data: CertificationComplianceInput) -> CertificationComplianceResult:
        """
        Analyzes mission profile, customer requirements, and aircraft concept
        to generate Certification Basis candidates, CCL items, and MoC plans.
        """
        
        # --- Langfuse Tracking Metadata Preparation ---
        # metadata = {
        #     "mission_id": getattr(input_data.mission_profile, "mission_id", input_data.run_id),
        #     "aircraft_concept_id": getattr(input_data.aircraft_concept, "concept_id", None) if input_data.aircraft_concept else None,
        #     "certification_db_version": "v1.0",
        #     "source_families_checked": input_data.certification_source_policy.allowed_source_families,
        #     "prompt_version": "v0.1.0",
        #     "schema_version": "v0.1.0"
        # }
        # ----------------------------------------------
        
        # [1] Certification Basis Selection
        basis_candidates = self.basis_selector.select(input_data)

        # [2] Clause Retrieval from Certification DB
        clauses = self.clause_retriever.retrieve(
            basis_candidates=basis_candidates,
            mission_profile=input_data.mission_profile,
            customer_requirements=input_data.customer_requirements,
            aircraft_concept=input_data.aircraft_concept,
        )

        # [3] Applicability Assessment
        ccl_items = self.applicability_assessor.assess(
            clauses=clauses,
            mission_profile=input_data.mission_profile,
            aircraft_concept=input_data.aircraft_concept,
            customer_requirements=input_data.customer_requirements,
        )

        # [4] Compliance Checklist Generation (Mapping or refinement step)
        ccl_items = self.ccl_builder.build(ccl_items)

        # [5] MoC Candidate Mapping
        moc_plans = self.moc_mapper.map(
            ccl_items=ccl_items,
            aircraft_concept=input_data.aircraft_concept,
        )

        # [6] Certification Risk Assessment
        risk_report = self.risk_assessor.assess(
            ccl_items=ccl_items,
            moc_plans=moc_plans,
        )

        # Traceability Linking
        trace_links = self.trace_linker.build(
            ccl_items=ccl_items,
            moc_plans=moc_plans,
            customer_requirements=input_data.customer_requirements,
        )

        # TODO: Implement the final LLM reasoning step using the deterministic outputs
        # and validate via Pydantic matching the CertificationComplianceResult schema.
        
        # Note on scoring for Langfuse (must be tracked separately via callbacks):
        # - schema_validity
        # - db_groundedness
        # - ccl_coverage
        # - moc_mapping_completeness
        # - hallucinated_clause_count (Must be 0)
        # - human_review_item_count
        # - simulation_supported_moc_count
        # - traceability_coverage_ratio

        raise NotImplementedError("The final result composition step is not yet implemented.")

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        LangGraph-compatible execution block.
        """
        input_data = state.get("certification_compliance_input")
        if input_data:
            state["certification_compliance_result"] = self.analyze(input_data)
        return state
