from pydantic import BaseModel

class CalculationRequest(BaseModel):
    operand1: float
    operand2: float
    operation: str

class CalculationResponse(BaseModel):
    result: float
