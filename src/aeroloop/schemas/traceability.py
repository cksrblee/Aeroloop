from typing import Literal, Optional
from pydantic import BaseModel

class TraceLink(BaseModel):
    trace_id: str

    source_type: str
    source_id: str

    target_type: str
    target_id: str

    relation_type: Literal[
        "derived_from",
        "supported_by",
        "merged_into",
        "conflicts_with",
        "compiled_to",
        "verified_by",
        "reported_in"
    ]

    rationale: Optional[str] = None
    confidence: Optional[float] = None

class TraceabilityMatrix(BaseModel):
    pass

class TraceabilityRow(BaseModel):
    pass

class CertificationRequirementLink(BaseModel):
    link_id: str

    ccl_item_id: str
    moc_id: Optional[str] = None

    related_customer_requirement_id: Optional[str] = None
    related_final_requirement_id: Optional[str] = None

    relation_type: Literal[
        "constrains",
        "verifies",
        "supports",
        "conflicts_with",
        "requires_follow_up"
    ]

    rationale: str

class CertificationConflict(BaseModel):
    conflict_id: str

    conflict_type: Literal[
        "customer_requirement_vs_certification",
        "design_feature_vs_clause",
        "missing_design_data",
        "moc_not_available",
        "applicability_uncertain"
    ]

    ccl_item_id: Optional[str] = None
    related_customer_requirement_id: Optional[str] = None

    description: str
    severity: Literal["low", "medium", "high", "critical"]

    recommended_action: str
