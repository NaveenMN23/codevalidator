from fastapi import APIRouter, HTTPException
from src.services.CalculatorService import CalculatorService
from src.dtos.CalculationDTO import CalculationDTO

router = APIRouter()

@router.post("/add", response_model=CalculationDTO)
def add(calculation: CalculationDTO):
    try:
        result = CalculatorService.add(calculation.operand1, calculation.operand2)
        return CalculationDTO(operand1=calculation.operand1, operand2=calculation.operand2, operation="add", result=result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
