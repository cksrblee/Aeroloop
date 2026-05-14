from pydantic import BaseModel

class Waypoint(BaseModel):
    pass

class FlightPath(BaseModel):
    pass

class PathPlanningRequest(BaseModel):
    pass

class PathPlanningResult(BaseModel):
    pass

class PathQualityMetrics(BaseModel):
    pass

class ReplanningTrigger(BaseModel):
    pass

class ReplanningResult(BaseModel):
    pass
