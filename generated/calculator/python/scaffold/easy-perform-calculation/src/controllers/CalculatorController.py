from fastapi import APIRouter, HTTPException
from src.services.CalculatorService import CalculatorService
from src.dtos.CalculationDTO import CalculationRequest, CalculationResponse

router = APIRouter()

@router.post("/calculate", response_model=CalculationResponse)
def calculate(calculation_request: CalculationRequest):
    try:
        result = CalculatorService.performCalculation(
            calculation_request.operand1,
            calculation_request.operand2,
            calculation_request.operation
        )
        return CalculationResponse(result=result)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
