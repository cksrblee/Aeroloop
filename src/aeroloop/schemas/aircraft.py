from typing import Literal, Optional
from pydantic import BaseModel

class AircraftConcept(BaseModel):
    concept_id: str

    aircraft_type: Literal[
        "evtol",
        "vtol",
        "rotorcraft",
        "fixed_wing",
        "lift_cruise",
        "multirotor",
        "tiltrotor",
        "unknown"
    ]

    mtow_kg: Optional[float] = None
    passenger_count: Optional[int] = None
    crew_count: Optional[int] = None

    propulsion_type: Literal[
        "electric",
        "hybrid_electric",
        "turbine",
        "piston",
        "unknown"
    ] = "unknown"

    number_of_engines: Optional[int] = None
    number_of_motors: Optional[int] = None
    number_of_lift_units: Optional[int] = None

    has_wing: Optional[bool] = None
    has_rotor: Optional[bool] = None
    vertical_takeoff_landing: Optional[bool] = None

    intended_operation: Literal[
        "passenger_transport",
        "cargo",
        "urban_air_mobility",
        "campus_air_mobility",
        "emergency_service",
        "unknown"
    ] = "unknown"

class AircraftTemplate(BaseModel):
    pass

class AircraftCandidate(BaseModel):
    pass

class CandidateScore(BaseModel):
    pass
