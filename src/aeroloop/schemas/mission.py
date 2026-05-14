from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
from .common import (
    Assumption, 
    MissingField, 
    ParsedFact,
    ParsedConstraint,
    Ambiguity,
    EvidenceSpan,
    RequirementSeed,
    RuntimeMonitoringCandidate
)

class MissionParsingInput(BaseModel):
    mission_id: str
    raw_user_input: str
    language: str = "ko"
    user_context: dict | None = None
    default_unit_system: str = "SI"
    project_context: dict | None = None

class ConfidenceSummary(BaseModel):
    overall_confidence: float
    low_confidence_fields: list[str] = []

class MissionProfile(BaseModel):
    # 1. Basic Mission Info
    operation_area: str | None = None
    origin: str | None = None
    destination: str | None = None
    mission_type: str | None = None
    vehicle_type_hint: str | None = None

    # 2. Transport Info
    passenger_count: int | None = None
    payload_kg: float | None = None
    cargo_type: str | None = None

    # 3. Flight Conditions
    mission_distance_m: float | None = None
    max_altitude_m: float | None = None
    min_altitude_m: float | None = None
    cruise_speed_mps: float | None = None
    max_speed_mps: float | None = None
    flight_time_limit_s: float | None = None

    # 4. Safety / Environmental Constraints
    minimum_obstacle_clearance_m: float | None = None
    minimum_building_clearance_m: float | None = None
    geofence_constraints: list[str] = []
    no_fly_zone_constraints: list[str] = []
    noise_constraints: list[str] = []
    weather_constraints: list[str] = []
    wind_constraints: list[str] = []

    # 5. Energy / Performance Conditions
    battery_reserve_at_destination_percent: float | None = None
    endurance_requirement_min: float | None = None
    range_requirement_m: float | None = None

class MissionParsingResult(BaseModel):
    mission_id: str
    raw_input: str
    mission_profile: MissionProfile
    
    explicit_constraints: list[ParsedConstraint] = []
    implicit_constraint_candidates: list[ParsedConstraint] = []
    
    missing_fields: list[MissingField] = []
    ambiguities: list[Ambiguity] = []
    assumptions: list[Assumption] = []
    evidence_spans: list[EvidenceSpan] = []
    
    requirement_seed_candidates: list[RequirementSeed] = []
    runtime_monitoring_candidates: list[RuntimeMonitoringCandidate] = []
    
    confidence_summary: ConfidenceSummary | None = None

