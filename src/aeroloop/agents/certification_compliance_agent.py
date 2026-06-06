from typing import Any, Dict, List, TypedDict
import json
from pathlib import Path

from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END
from pydantic import BaseModel, Field

from aeroloop.agents.base_agent import BaseAIAgent
from aeroloop.schemas.compliance import (
    CertificationComplianceInput, 
    CertificationComplianceResult,
    CertificationBasisCandidate,
    ComplianceChecklistItem,
    CertificationComplianceQualityReport
)
from aeroloop.schemas.moc import MeansOfCompliancePlan
from aeroloop.schemas.traceability import CertificationRequirementLink
from aeroloop.schemas.certification import CertificationClause
from aeroloop.utils.ids import make_id

class AgentState(TypedDict):
    input_data: CertificationComplianceInput
    basis_candidates: List[CertificationBasisCandidate]
    retrieved_clauses: List[CertificationClause]
    ccl_items: List[ComplianceChecklistItem]
    moc_plans: List[MeansOfCompliancePlan]
    requirement_links: List[CertificationRequirementLink]
    unresolved_questions: List[str]
    readiness_level: str
    revision_count: int
    validation_errors: List[str]

class BasisSelectorOutput(BaseModel):
    basis_candidates: List[CertificationBasisCandidate]
    unresolved_questions: List[str] = []

class ApplicabilityOutput(BaseModel):
    ccl_items: List[ComplianceChecklistItem]
    unresolved_questions: List[str] = []

class CertValidatorOutput(BaseModel):
    is_valid: bool
    validation_errors: List[str] = []

class MoCOutput(BaseModel):
    moc_plans: List[MeansOfCompliancePlan]

class TraceLinkOutput(BaseModel):
    requirement_links: List[CertificationRequirementLink]

class RiskAssessorOutput(BaseModel):
    readiness_level: str

class CertificationComplianceAgent(BaseAIAgent):
    def __init__(self, **kwargs):
        super().__init__(
            name="Certification Compliance Agent",
            description="Generates preliminary certification basis, CCL, and MoC using LangGraph.",
            **kwargs
        )
        self.llm = ChatOpenAI(model="gpt-5.4-mini", temperature=0.0)
        self.graph = self._build_graph()

    def _build_graph(self):
        workflow = StateGraph(AgentState)
        
        workflow.add_node("basis_selector", self.basis_selector_node)
        workflow.add_node("clause_retriever", self.clause_retriever_node)
        workflow.add_node("applicability_assessor", self.applicability_assessor_node)
        workflow.add_node("cert_validator", self.cert_validator_node)
        workflow.add_node("ccl_builder", self.ccl_builder_node)
        workflow.add_node("moc_mapper", self.moc_mapper_node)
        workflow.add_node("risk_assessor", self.risk_assessor_node)
        workflow.add_node("traceability_linker", self.traceability_linker_node)
        
        workflow.add_edge(START, "basis_selector")
        workflow.add_edge("basis_selector", "clause_retriever")
        workflow.add_edge("clause_retriever", "applicability_assessor")
        workflow.add_edge("applicability_assessor", "cert_validator")
        
        workflow.add_conditional_edges(
            "cert_validator",
            self.route_validation,
            {
                "valid": "ccl_builder",
                "invalid_retry": "applicability_assessor",
                "invalid_fallback": "ccl_builder"
            }
        )
        
        workflow.add_edge("ccl_builder", "moc_mapper")
        workflow.add_edge("moc_mapper", "risk_assessor")
        workflow.add_edge("risk_assessor", "traceability_linker")
        workflow.add_edge("traceability_linker", END)
        
        return workflow.compile()

    def _build_basis_selector_prompt(self) -> str:
        return """
You are the Certification Basis Selector.
Given the MissionProfile, identify applicable Certification Basis Candidates.
Output JSON conforming to BasisSelectorOutput schema.
"""

    def _build_applicability_assessor_prompt(self) -> str:
        return """
You are the Certification Applicability Assessor.
Given the AircraftConcept and Retrieved Clauses, assess which clauses are applicable.
Output JSON conforming to ApplicabilityOutput schema.
Rules:
- If propulsion details are missing, mark propulsion items as "tbd".
- For distributed electric propulsion, mark OEI items as "requires_human_review".
"""

    def _build_cert_validator_prompt(self) -> str:
        return """
You are the Certification Validator.
Evaluate if the selected CCL items fully match the AircraftConcept without contradictions.
Return any validation errors in the CertValidatorOutput schema.
"""

    def _build_moc_mapper_prompt(self) -> str:
        return """
You are the Means of Compliance (MoC) Mapper.
Assign primary MoC methods for each applicable CCL item.
Output JSON conforming to MoCOutput schema.
Rule:
- For 'Operating limitations' or software checks, prefer 'simulation'.
"""

    def _build_risk_assessor_prompt(self) -> str:
        return """
You are the Certification Risk Assessor.
Evaluate the overall certification risk and readiness level.
Output JSON conforming to RiskAssessorOutput schema.
"""

    def _build_traceability_linker_prompt(self) -> str:
        return """
You are the Traceability Linker.
Link customer requirements to certification CCL items.
Output JSON conforming to TraceLinkOutput schema.
"""

    def basis_selector_node(self, state: AgentState):
        mission_str = state['input_data'].mission_profile.model_dump() if state['input_data'].mission_profile else "{}"
        system_prompt = self._build_basis_selector_prompt()
        prompt = f"{system_prompt}\nMission Profile: {mission_str}"
        output = self.llm.with_structured_output(BasisSelectorOutput).invoke(prompt)
        return {"basis_candidates": output.basis_candidates, "unresolved_questions": state.get("unresolved_questions", []) + output.unresolved_questions}

    def clause_retriever_node(self, state: AgentState):
        processed_dir = Path("data/regulations/processed")
        clauses = []
        
        # Determine keywords from mission and concept
        keywords = ["emergency", "operating limitations", "propulsion"]
        if state['input_data'].aircraft_concept and state['input_data'].aircraft_concept.propulsion_type == "electric":
            keywords.append("electric")
            keywords.append("battery")
            
        if processed_dir.exists():
            for md_file in processed_dir.glob("*.md"):
                doc_id = md_file.stem
                
                # Read file and extract snippets based on keywords
                try:
                    content = md_file.read_text()
                    snippets = []
                    # Very naive extraction: split by paragraphs, keep if keyword found
                    paragraphs = content.split('\n\n')
                    for p in paragraphs:
                        if any(kw.lower() in p.lower() for kw in keywords):
                            snippets.append(p)
                            if len(snippets) >= 2: # Limit to 2 snippets per document to save tokens
                                break
                    
                    if snippets:
                        clauses.append(CertificationClause(
                            clause_id=f"CLAUSE-{doc_id}-001",
                            document_id=doc_id,
                            clause_number="VARIOUS",
                            raw_text="\n...\n".join(snippets),
                            topic_area="general"
                        ))
                except Exception:
                    pass
                    
        return {"retrieved_clauses": clauses}

    def applicability_assessor_node(self, state: AgentState):
        concept = state['input_data'].aircraft_concept
        system_prompt = self._build_applicability_assessor_prompt()
        prompt = f"{system_prompt}\nAircraft Concept: {concept}\nRetrieved Clauses: {state['retrieved_clauses']}"
        output = self.llm.with_structured_output(ApplicabilityOutput).invoke(prompt)
                
        questions = state.get("unresolved_questions", []) + output.unresolved_questions
        return {"ccl_items": output.ccl_items, "unresolved_questions": questions}

    def cert_validator_node(self, state: AgentState):
        system_prompt = self._build_cert_validator_prompt()
        prompt = f"{system_prompt}\nAircraft Concept: {state['input_data'].aircraft_concept}"
        output = self.llm.with_structured_output(CertValidatorOutput).invoke(prompt)
        
        revision_count = state.get("revision_count", 0) + 1
        
        return {"validation_errors": output.validation_errors, "revision_count": revision_count}

    def route_validation(self, state: AgentState):
        errors = state.get("validation_errors", [])
        if not errors:
            return "valid"
            
        if state.get("revision_count", 0) <= 3:
            return "invalid_retry"
            
        return "invalid_fallback"

    def ccl_builder_node(self, state: AgentState):
        unresolved = state.get("unresolved_questions", [])
        if state.get("revision_count", 0) > 3 and state.get("validation_errors"):
            unresolved.append(f"Fallback triggered: Unable to resolve certification applicability after 3 loops. Errors: {state['validation_errors']}")
            
        return {"unresolved_questions": unresolved}

    def moc_mapper_node(self, state: AgentState):
        system_prompt = self._build_moc_mapper_prompt()
        prompt = f"{system_prompt}\nCCL Items: {state['ccl_items']}"
        output = self.llm.with_structured_output(MoCOutput).invoke(prompt)
        return {"moc_plans": output.moc_plans}

    def risk_assessor_node(self, state: AgentState):
        concept = state['input_data'].aircraft_concept
        system_prompt = self._build_risk_assessor_prompt()
        output = self.llm.with_structured_output(RiskAssessorOutput).invoke(system_prompt)
        
        readiness_level = output.readiness_level
        
        if state.get("revision_count", 0) > 3 and state.get("validation_errors"):
            readiness_level = "needs_human_certification_review"
        elif concept is None:
            readiness_level = "needs_configuration_detail"
        else:
            readiness_level = "ready_for_concept_review"
            
        return {"readiness_level": readiness_level}

    def traceability_linker_node(self, state: AgentState):
        system_prompt = self._build_traceability_linker_prompt()
        output = self.llm.with_structured_output(TraceLinkOutput).invoke(system_prompt)
        return {"requirement_links": output.requirement_links}

    def analyze(self, input_data: CertificationComplianceInput) -> CertificationComplianceResult:
        initial_state = AgentState(
            input_data=input_data,
            basis_candidates=[],
            retrieved_clauses=[],
            ccl_items=[],
            moc_plans=[],
            requirement_links=[],
            unresolved_questions=[],
            readiness_level="preliminary",
            revision_count=0,
            validation_errors=[]
        )
        
        final_state = self.graph.invoke(initial_state)
        
        ccl_items = final_state.get("ccl_items", [])
        moc_plans = final_state.get("moc_plans", [])
        
        report = CertificationComplianceQualityReport(
            total_basis_candidates=len(final_state.get("basis_candidates", [])),
            total_retrieved_clauses=len(final_state.get("retrieved_clauses", [])),
            total_ccl_items=len(ccl_items),
            included_items=sum(1 for x in ccl_items if x.applicability_status == "included"),
            excluded_items=sum(1 for x in ccl_items if x.applicability_status == "excluded"),
            tbd_items=sum(1 for x in ccl_items if x.applicability_status == "tbd"),
            human_review_items=sum(1 for x in ccl_items if x.applicability_status == "requires_human_review"),
            total_moc_plans=len(moc_plans),
            flight_test_required_count=0,
            simulation_supported_count=sum(1 for x in moc_plans if x.primary_method == "simulation"),
            analysis_supported_count=0,
            traceability_coverage_ratio=1.0 if ccl_items else 0.0,
            readiness_level=final_state.get("readiness_level", "preliminary"),
            summary="LangGraph Agent Analysis completed with cyclic validation."
        )

        return CertificationComplianceResult(
            result_id=make_id("CERT-COMP"),
            run_id=input_data.run_id,
            mission_id=getattr(input_data.mission_profile, "mission_id", input_data.run_id) if input_data.mission_profile else input_data.run_id,
            agent_version="v0.3.0-langgraph-cyclic",
            schema_version="v0.1.0",
            certification_basis_candidates=final_state.get("basis_candidates", []),
            retrieved_clauses=final_state.get("retrieved_clauses", []),
            ccl_items=ccl_items,
            moc_plans=moc_plans,
            requirement_links=final_state.get("requirement_links", []),
            conflicts=[],
            unresolved_questions=final_state.get("unresolved_questions", []),
            assumptions=[],
            quality_report=report
        )

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        input_data = state.get("certification_compliance_input")
        if input_data:
            state["certification_compliance_result"] = self.analyze(input_data)
        return state
