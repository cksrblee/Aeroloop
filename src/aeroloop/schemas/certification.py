from typing import Optional, List, Literal
from pydantic import BaseModel

class CertificationDocument(BaseModel):
    document_id: str
    title: str
    authority: str
    jurisdiction: str
    version: str | None = None
    issue_date: str | None = None
    document_type: str
    aircraft_categories: list[str] = []
    source_path: str | None = None
    source_url: str | None = None

class CertificationClause(BaseModel):
    clause_id: str
    document_id: str
    section_id: str
    section_title: str | None = None
    raw_text: str
    normalized_summary: str | None = None
    keywords: list[str] = []
    requirement_area: str
    applicability_tags: list[str] = []

class CertificationQueryContext(BaseModel):
    jurisdiction_hint: str | None = None
    aircraft_category_hint: str | None = None
    operation_type_hint: str | None = None
    candidate_aircraft_type: str | None = None

class ApplicabilityResult(BaseModel):
    applicability_id: str
    clause_id: str
    mission_id: str
    applicability: Literal[
        "applicable",
        "potentially_applicable",
        "unclear",
        "not_applicable"
    ]
    confidence: float
    reason: str
    required_follow_up: list[str] = []

from .requirement import CandidateRequirement
from .regulation import RegulationEvidence

class CertificationRequirementResult(BaseModel):
    candidate_requirements: list[CandidateRequirement]
    regulation_evidence: list[RegulationEvidence]
    applicability_results: list[ApplicabilityResult]
    unresolved_certification_questions: list[str]
