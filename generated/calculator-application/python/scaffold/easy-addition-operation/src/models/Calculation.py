from pydantic import BaseModel

class Calculation(BaseModel):
    id: int
    operation: str
    operand1: float
    operand2: float
    result: float
