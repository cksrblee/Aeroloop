from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime
from .common import Assumption, MissingField, ParsedFact

class RawMissionInput(BaseModel):
    input_id: str
    raw_text: str
    language: str = "ko"
    submitted_at: datetime

class MissionProfile(BaseModel):
    mission_id: str
    raw_input_id: str

    operation_area: str | None = None
    operation_type: str | None = None
    vehicle_type_hint: str | None = None

    origin: str | None = None
    destination: str | None = None

    passenger_count: int | None = None
    payload_kg: float | None = None
    mission_distance_km: float | None = None

    max_altitude_m: float | None = None
    cruise_speed_mps: float | None = None
    max_speed_mps: float | None = None

    noise_constraint: str | None = None
    safety_constraints: list[str] = []
    environmental_constraints: list[str] = []
    operational_constraints: list[str] = []

    priority: list[str] = []

    assumptions: list[Assumption] = []
    missing_fields: list[MissingField] = []

class MissionParsingResult(BaseModel):
    mission_profile: MissionProfile
    parsed_facts: list[ParsedFact]
    missing_fields: list[MissingField]
    assumptions: list[Assumption]
