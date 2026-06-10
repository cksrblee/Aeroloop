from typing import TypedDict, Annotated, Any
import operator
from aeroloop.schemas.mission import MissionProfile, MissionParsingInput
from aeroloop.schemas.requirement import CandidateRequirement, FinalRequirement, RequirementConflict, RequirementReasoningResult
from aeroloop.schemas.common import Assumption, ErrorInfo
from aeroloop.schemas.regulation import RegulationEvidence
from aeroloop.schemas.compliance import CertificationComplianceResult, CertificationValidationResult
from aeroloop.schemas.aircraft import AircraftConcept
from aeroloop.schemas.engineering import SizingAgentResult
from aeroloop.schemas.geometry import GeometryDesignResult
from aeroloop.schemas.aerodynamics import AerodynamicsAnalysisResult
from aeroloop.schemas.traceability import TraceabilityRegistry

def add_items(a: list | None, b: list | None) -> list:
    """Merge two lists safely for LangGraph state."""
    res = []
    if a is not None:
        res.extend(a)
    if b is not None:
        res.extend(b)
    return res

class WorkflowState(TypedDict):
    """
    Global state for the bidirectional LangGraph workflow.
    """
    run_id: str
    raw_input: MissionParsingInput
    mission_profile: MissionProfile | None
    mission_parsing_result: Any | None
    aircraft_concept: AircraftConcept | None
    certification_compliance_result: CertificationComplianceResult | None
    requirement_reasoning_result: RequirementReasoningResult | None
    certification_validation_result: CertificationValidationResult | None
    sizing_result: SizingAgentResult | None
    geometry_design_result: GeometryDesignResult | None
    analysis_result: AerodynamicsAnalysisResult | None
    
    # Cyclic iteration trackers
    sizing_iteration_count: int | None
    global_iteration_count: int | None
    
    # Traceability and DB
    traceability_registry: TraceabilityRegistry | None
    
    candidate_requirements: list[CandidateRequirement] | None
    final_requirements: list[FinalRequirement] | None
    regulation_evidence: list[RegulationEvidence] | None
    conflicts: list[RequirementConflict] | None
    assumptions: list[Assumption] | None
    errors: list[ErrorInfo] | None
    unresolved_questions: list[str] | None
    
    full_auto: bool | None
    
    # HITL Control
    human_input: str | None
    awaiting_input_from: str | None
    
    # Bidirectional Routing Variables
    feedback_history: Annotated[list[str], add_items]
    next_node: str | None
    status: str
