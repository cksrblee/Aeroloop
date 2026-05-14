from enum import Enum
from typing import List, Optional
from pydantic import BaseModel

from .common import Assumption, MissingField, ParsedFact, ErrorInfo
from .mission import MissionParsingInput, MissionProfile
from .requirement import CandidateRequirement, FinalRequirement, RequirementConflict
from .regulation import RegulationEvidence
from .certification import ApplicabilityResult
from .traceability import TraceLink

class WorkflowStage(str, Enum):
    INITIALIZED = "initialized"
    MISSION_PARSED = "mission_parsed"
    CUSTOMER_REQUIREMENTS_GENERATED = "customer_requirements_generated"
    CERTIFICATION_REQUIREMENTS_GENERATED = "certification_requirements_generated"
    REQUIREMENTS_REASONED = "requirements_reasoned"
    REQUIREMENTS_FINALIZED = "requirements_finalized"
    FAILED = "failed"

class WorkflowState(BaseModel):
    run_id: str
    current_stage: str
    raw_input: MissionParsingInput
    mission_profile: MissionProfile | None = None
    candidate_requirements: list[CandidateRequirement] = []
    regulation_evidence: list[RegulationEvidence] = []
    final_requirements: list[FinalRequirement] = []
    conflicts: list[RequirementConflict] = []
    assumptions: list[Assumption] = []
    errors: list[ErrorInfo] = []

class RequirementBlackboard(BaseModel):
    run_id: str
    raw_input: MissionParsingInput

    mission_profile: MissionProfile | None = None
    parsed_facts: list[ParsedFact] = []

    customer_requirement_candidates: list[CandidateRequirement] = []
    certification_requirement_candidates: list[CandidateRequirement] = []
    environment_requirement_candidates: list[CandidateRequirement] = []

    regulation_evidence: list[RegulationEvidence] = []
    applicability_results: list[ApplicabilityResult] = []

    conflicts: list[RequirementConflict] = []
    assumptions: list[Assumption] = []
    missing_fields: list[MissingField] = []

    final_requirements: list[FinalRequirement] = []
    trace_links: list[TraceLink] = []
