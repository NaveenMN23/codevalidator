from fastapi import APIRouter, HTTPException
from src.services.CalculatorService import perform_calculation
from src.dtos.CalculationDTO import CalculationRequest, CalculationResponse

router = APIRouter()

@router.post("/calculate", response_model=CalculationResponse)
def calculate(calculation_request: CalculationRequest):
    try:
        result = perform_calculation(
            calculation_request.operation,
            calculation_request.operand1,
            calculation_request.operand2
        )
        return CalculationResponse(result=result)
    except InvalidOperationException as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ZeroDivisionError:
        raise HTTPException(status_code=400, detail="Division by zero is not allowed.")
