from pydantic import BaseModel

class SimulationConfig(BaseModel):
    pass

class SimulationRun(BaseModel):
    pass

class FlightState(BaseModel):
    pass

class SimulationRunLog(BaseModel):
    pass

class SimulationEvent(BaseModel):
    pass

class TelemetrySeries(BaseModel):
    pass
