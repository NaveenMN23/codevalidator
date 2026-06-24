from src.repositories.CalculationRepository import CalculationRepository

class CalculatorService:
    @staticmethod
    def add(operand1: float, operand2: float) -> float:
        """Perform addition of two numbers and store the result."""
        if not isinstance(operand1, (int, float)) or not isinstance(operand2, (int, float)):
    raise ValueError("Operands must be numbers")
result = operand1 + operand2
calculation = Calculation(id=0, operation='add', operand1=operand1, operand2=operand2, result=result)
CalculationRepository.save(calculation)
return result

