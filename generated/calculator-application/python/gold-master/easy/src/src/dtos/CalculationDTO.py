from pydantic import BaseModel

class CalculationRequest(BaseModel):
    operation: str
    operand1: float
    operand2: float

class CalculationResponse(BaseModel):
    result: float
