from typing import Literal, Optional, List
from pydantic import BaseModel

from .aircraft import AircraftConcept, ConceptBaseline
from .certification import CertificationSourcePolicy, CertificationClause
from .moc import MeansOfCompliancePlan
from .traceability import CertificationRequirementLink, CertificationConflict

# Assume MissionProfile and CandidateRequirement are defined in respective files
from .mission import MissionProfile
from .requirement import CandidateRequirement

class CertificationComplianceInput(BaseModel):
    run_id: str
    mission_profile: MissionProfile
    customer_requirements: List[CandidateRequirement]

    aircraft_concept: Optional[AircraftConcept] = None

    jurisdiction_hint: Literal[
        "EASA",
        "FAA",
        "KAS",
        "AUTO"
    ] = "AUTO"

    certification_source_policy: CertificationSourcePolicy

class CertificationBasisCandidate(BaseModel):
    basis_id: str

    source_family: Literal[
        "SC_VTOL_SMALL",
        "SMALL_ROTORCRAFT",
        "SMALL_AIRCRAFT"
    ]

    authority: Literal["EASA", "FAA", "KAS"]
    document_ids: List[str]

    applicability: Literal[
        "primary",
        "secondary_reference",
        "comparison_reference",
        "not_applicable",
        "uncertain"
    ]

    confidence: float
    rationale: str

    unresolved_questions: List[str] = []

class ComplianceChecklistItem(BaseModel):
    ccl_item_id: str
    run_id: str

    basis_id: str
    document_id: str
    clause_id: str
    clause_number: str
    clause_title: Optional[str] = None

    topic_area: str

    applicability_status: Literal[
        "included",
        "excluded",
        "not_applicable",
        "tbd",
        "requires_human_review"
    ]

    applicability_rationale: str

    related_customer_requirement_ids: List[str] = []
    related_mission_fields: List[str] = []

    design_relevance: Literal[
        "direct_design_driver",
        "verification_only",
        "report_only",
        "not_relevant_yet"
    ]

    compliance_status: Literal[
        "not_started",
        "planned",
        "partially_supported",
        "supported_by_poc",
        "requires_test",
        "requires_analysis",
        "requires_human_review"
    ] = "not_started"

    risk_level: Literal[
        "low",
        "medium",
        "high",
        "critical"
    ]

    notes: List[str] = []

class CertificationComplianceQualityReport(BaseModel):
    total_basis_candidates: int
    total_retrieved_clauses: int
    total_ccl_items: int
    included_items: int
    excluded_items: int
    tbd_items: int
    human_review_items: int

    total_moc_plans: int
    flight_test_required_count: int
    simulation_supported_count: int
    analysis_supported_count: int

    traceability_coverage_ratio: float

    readiness_level: Literal[
        "preliminary",
        "ready_for_concept_review",
        "needs_configuration_detail",
        "needs_human_certification_review"
    ]

    summary: str

class CertificationComplianceResult(BaseModel):
    result_id: str
    run_id: str
    mission_id: str

    agent_name: str = "CertificationComplianceAgent"
    agent_version: str
    schema_version: str

    certification_basis_candidates: List[CertificationBasisCandidate]

    retrieved_clauses: List[CertificationClause]
    ccl_items: List[ComplianceChecklistItem]
    moc_plans: List[MeansOfCompliancePlan]

    requirement_links: List[CertificationRequirementLink]
    conflicts: List[CertificationConflict]

    unresolved_questions: List[str]
    assumptions: List[str]

    quality_report: CertificationComplianceQualityReport

class CertificationValidationInput(BaseModel):
    run_id: str
    concept_baseline: ConceptBaseline
    compliance_result: CertificationComplianceResult

class CertificationValidationResult(BaseModel):
    validation_id: str
    run_id: str
    is_valid: bool
    violations: List[str] = []
    warnings: List[str] = []
    status: Literal["success", "failed"]
