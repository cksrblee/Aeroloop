from typing import Literal, Any, Dict, List, Optional
from pydantic import BaseModel

class Assumption(BaseModel):
    assumption_id: str
    text: str
    source: str
    related_object_ids: list[str] = []
    confidence: float | None = None

class MissingField(BaseModel):
    field_name: str
    object_type: str
    reason: str
    required_for: list[str] = []
    severity: Literal["low", "medium", "high", "critical"] = "medium"

class ParsedFact(BaseModel):
    fact_id: str
    field_name: str
    value: str | int | float | bool
    unit: str | None = None
    source_text: str
    confidence: float

class ErrorInfo(BaseModel):
    error_id: str
    module_name: str
    message: str
    recoverable: bool
    details: dict = {}
