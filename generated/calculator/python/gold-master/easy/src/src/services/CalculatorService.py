from src.exceptions.InvalidOperationException import InvalidOperationException

def performCalculation(operand1: float, operand2: float, operation: str) -> float:
    """Perform a calculation based on the operation type.

    Supported operations: add, subtract, multiply, divide.
    Handle division by zero and invalid operations.
    """
    if operation == 'add':
    return operand1 + operand2
elif operation == 'subtract':
    return operand1 - operand2
elif operation == 'multiply':
    return operand1 * operand2
elif operation == 'divide':
    if operand2 == 0:
        raise ZeroDivisionError("Cannot divide by zero")
    return operand1 / operand2
else:
    raise InvalidOperationException(operation)
