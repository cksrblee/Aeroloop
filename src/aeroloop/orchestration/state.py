from typing import TypedDict, Annotated
import operator
from aeroloop.schemas.mission import MissionProfile, MissionParsingInput
from aeroloop.schemas.requirement import CandidateRequirement, FinalRequirement, RequirementConflict
from aeroloop.schemas.common import Assumption, ErrorInfo
from aeroloop.schemas.regulation import RegulationEvidence

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
    
    candidate_requirements: Annotated[list[CandidateRequirement], add_items]
    final_requirements: Annotated[list[FinalRequirement], add_items]
    regulation_evidence: Annotated[list[RegulationEvidence], add_items]
    conflicts: Annotated[list[RequirementConflict], add_items]
    assumptions: Annotated[list[Assumption], add_items]
    errors: Annotated[list[ErrorInfo], add_items]
    
    # Bidirectional Routing Variables
    feedback_history: Annotated[list[str], add_items]
    next_node: str | None
    status: str
