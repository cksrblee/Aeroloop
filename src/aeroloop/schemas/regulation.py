from typing import Literal, Optional
from pydantic import BaseModel

class RegulationEvidence(BaseModel):
    evidence_id: str
    clause_id: str
    document_id: str
    source_name: str
    section_id: str | None = None
    text_snippet: str
    relevance_score: float
    applicability: Literal[
        "applicable",
        "potentially_applicable",
        "unclear",
        "not_applicable"
    ]
    rationale: str | None = None
