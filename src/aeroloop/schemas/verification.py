from pydantic import BaseModel

class RuntimeRule(BaseModel):
    pass

class RuleEvaluationResult(BaseModel):
    pass

class ViolationEvent(BaseModel):
    pass

class VerificationReport(BaseModel):
    pass
