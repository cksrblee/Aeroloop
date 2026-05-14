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

    rationale: str | None = None
    confidence: float | None = None

class TraceabilityMatrix(BaseModel):
    pass

class TraceabilityRow(BaseModel):
    pass
