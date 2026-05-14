from typing import Literal, List, Optional
from pydantic import BaseModel

from .common import Assumption, MissingField
from .mission import MissionProfile
from .regulation import RegulationEvidence
from .traceability import TraceLink

class CandidateRequirement(BaseModel):
    candidate_id: str
    proposed_by: Literal[
        "MissionParsingAgent",
        "CustomerRequirementAgent",
        "CertificationRequirementAgent",
        "AirspaceEnvironmentAgent",
        "System"
    ]

    source_type: Literal[
        "mission_input",
        "customer_requirement",
        "certification_db",
        "airspace_db",
        "environment_db",
        "system_assumption"
    ]

    source_refs: list[str] = []

    category: str
    title: str
    raw_requirement_text: str
    normalized_requirement: str

    requirement_type: Literal[
        "hard_constraint",
        "soft_objective",
        "report_only",
        "needs_clarification"
    ]

    variable_name: str | None = None
    operator: Literal["<", "<=", ">", ">=", "==", "!=", "in", "not_in"] | None = None
    threshold: float | int | str | bool | None = None
    unit: str | None = None

    verification_target: Literal[
        "aircraft_candidate",
        "engineering_calculation",
        "path_planning",
        "runtime_simulation",
        "path_planning_and_runtime_simulation",
        "report_only",
        "manual_review"
    ]

    priority: Literal["low", "medium", "high", "critical"]
    severity: Literal["low", "medium", "high", "critical"]

    applicability: Literal[
        "applicable",
        "potentially_applicable",
        "unclear",
        "not_applicable"
    ] = "applicable"

    confidence: float
    rationale: str

    assumptions: list[str] = []
    unresolved_issues: list[str] = []

class CustomerRequirementResult(BaseModel):
    candidate_requirements: list[CandidateRequirement]
    assumptions: list[Assumption]
    unresolved_questions: list[str]


class FinalRequirement(BaseModel):
    requirement_id: str
    mission_id: str

    title: str
    description: str
    category: str

    requirement_type: Literal[
        "hard_constraint",
        "soft_objective",
        "report_only",
        "manual_review"
    ]

    variable_name: str | None = None
    operator: Literal["<", "<=", ">", ">=", "==", "!=", "in", "not_in"] | None = None
    threshold: float | int | str | bool | None = None
    unit: str | None = None

    verification_target: Literal[
        "aircraft_candidate",
        "engineering_calculation",
        "path_planning",
        "runtime_simulation",
        "path_planning_and_runtime_simulation",
        "report_only",
        "manual_review"
    ]

    priority: Literal["low", "medium", "high", "critical"]
    severity: Literal["low", "medium", "high", "critical"]

    source_candidate_ids: list[str]
    evidence_refs: list[str] = []

    runtime_rule_ready: bool
    rationale: str

    assumptions: list[str] = []
    unresolved_issues: list[str] = []

class RequirementConflict(BaseModel):
    conflict_id: str
    conflict_type: Literal[
        "hard_vs_hard",
        "hard_vs_soft",
        "soft_vs_soft",
        "threshold_conflict",
        "objective_conflict",
        "missing_information"
    ]

    involved_candidate_ids: list[str]
    involved_requirement_ids: list[str] = []

    description: str
    severity: Literal["low", "medium", "high", "critical"]

    resolution_strategy: Literal[
        "safety_over_efficiency",
        "certification_over_customer_preference",
        "use_stricter_threshold",
        "convert_to_soft_objective",
        "requires_user_clarification",
        "manual_review_required"
    ]

    resolution_result: str | None = None
    resolved: bool = False

class RequirementQualityReport(BaseModel):
    total_candidate_requirements: int
    total_final_requirements: int

    hard_constraints: int
    soft_objectives: int
    report_only_requirements: int

    measurable_requirements: int
    non_measurable_requirements: int

    runtime_rule_ready_count: int
    unresolved_conflicts: int

    missing_critical_fields: list[str] = []

    readiness_for_simulation: Literal[
        "ready",
        "ready_with_assumptions",
        "needs_user_clarification",
        "not_ready"
    ]

    summary: str


from .certification import ApplicabilityResult


class RequirementAnalysisResult(BaseModel):
    result_id: str
    run_id: str
    mission_id: str

    mission_profile: MissionProfile

    candidate_requirements: list[CandidateRequirement]
    final_requirements: list[FinalRequirement]

    regulation_evidence: list[RegulationEvidence]
    applicability_results: list[ApplicabilityResult]

    conflicts: list[RequirementConflict]
    assumptions: list[Assumption]
    missing_fields: list[MissingField]

    trace_links: list[TraceLink]
    quality_report: RequirementQualityReport

class RequirementReasoningResult(BaseModel):
    final_requirements: list[FinalRequirement]
    conflicts: list[RequirementConflict]
    assumptions: list[Assumption]
    trace_links: list[TraceLink]
    quality_report: RequirementQualityReport
