from typing import Literal, Any, Dict, List, Optional
from pydantic import BaseModel, Field

class Assumption(BaseModel):
    assumption_id: str
    text: str
    source: str
    related_object_ids: list[str] = []
    confidence: float | None = None

class MissingField(BaseModel):
    field_name: str
    reason: str
    required_for: list[str] = []
    priority: str = "medium"
    suggested_question: str | None = None

class ParsedFact(BaseModel):
    fact_id: str
    field_name: str
    value: str | int | float | bool
    unit: str | None = None
    source_text: str
    confidence: float

class ParsedConstraint(BaseModel):
    constraint_id: str
    source_text: str
    constraint_type: str
    subject: str
    variable: str
    operator: str
    value: float | str | None = None
    unit: str | None = None
    normalized_value: float | None = None
    normalized_unit: str | None = None
    is_explicit: bool
    confidence: float

class Ambiguity(BaseModel):
    text_span: str
    ambiguity_type: str
    possible_interpretations: list[str]
    impact: str
    needs_clarification: bool

class EvidenceSpan(BaseModel):
    field_name: str
    value: str | float | int
    source_text: str
    start_char: int | None = None
    end_char: int | None = None
    confidence: float

class RequirementSeed(BaseModel):
    seed_id: str
    source: str
    category: str
    raw_statement: str
    parsed_variable: str | None = None
    parsed_condition: str | None = None
    target_downstream_agent: list[str] = []
    confidence: float

class RuntimeMonitoringCandidate(BaseModel):
    requirement_seed_id: str
    monitorable: bool
    simulation_variable: str | None = None
    violation_condition: str | None = None
    required_data_source: list[str] = []

class ErrorInfo(BaseModel):
    error_id: str
    module_name: str
    message: str
    recoverable: bool
    details: dict = {}

