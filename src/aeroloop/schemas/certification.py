from typing import Literal, Optional, List
from pydantic import BaseModel

class CertificationBasisDocument(BaseModel):
    document_id: str

    source_family: Literal[
        "SC_VTOL_SMALL",
        "SMALL_ROTORCRAFT",
        "SMALL_AIRCRAFT"
    ]

    authority: Literal["EASA", "FAA", "KAS"]
    document_name: str
    document_version: Optional[str] = None
    issue_date: Optional[str] = None

    aircraft_scope: List[str]
    operation_scope: List[str]

    source_url: Optional[str] = None
    local_path: Optional[str] = None

class CertificationClause(BaseModel):
    clause_id: str
    document_id: str

    clause_number: str
    clause_title: Optional[str] = None
    raw_text: str
    summary: Optional[str] = None

    subpart: Optional[str] = None
    topic_area: Literal[
        "general",
        "flight",
        "performance",
        "controllability",
        "structures",
        "design_and_construction",
        "powerplant",
        "propulsion",
        "energy_storage",
        "systems_and_equipment",
        "flight_controls",
        "software",
        "occupant_safety",
        "operating_limitations",
        "continued_airworthiness",
        "noise",
        "emergency_operation",
        "unknown"
    ]

    keywords: List[str] = []
    applicability_tags: List[str] = []

class ClauseApplicabilityRule(BaseModel):
    rule_id: str
    clause_id: str

    applies_to_aircraft_types: List[str] = []
    applies_to_operations: List[str] = []

    min_passenger_count: Optional[int] = None
    max_passenger_count: Optional[int] = None

    mtow_min_kg: Optional[float] = None
    mtow_max_kg: Optional[float] = None

    required_features: List[str] = []
    exclusion_features: List[str] = []

    example_exclusion_reason: Optional[str] = None

class CertificationSourcePolicy(BaseModel):
    allowed_source_families: List[Literal[
        "SC_VTOL_SMALL",
        "SMALL_ROTORCRAFT",
        "SMALL_AIRCRAFT"
    ]]

    allowed_authorities: List[Literal[
        "EASA",
        "FAA",
        "KAS"
    ]]

    strict_db_only: bool = True
    allow_cross_reference: bool = True
