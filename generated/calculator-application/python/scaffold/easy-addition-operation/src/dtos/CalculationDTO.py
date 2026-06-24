from pydantic import BaseModel

class CalculationDTO(BaseModel):
    operand1: float
    operand2: float
    operation: str
    result: float = None
