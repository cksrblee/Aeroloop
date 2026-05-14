from pydantic import BaseModel

class RunContext(BaseModel):
    pass

class ArtifactRef(BaseModel):
    pass

class ErrorInfo(BaseModel):
    pass

class ModuleStatus(BaseModel):
    pass

class Assumption(BaseModel):
    pass

class MissingField(BaseModel):
    pass
