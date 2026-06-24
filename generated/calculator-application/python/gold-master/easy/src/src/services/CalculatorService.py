from src.exceptions.InvalidOperationException import InvalidOperationException

def perform_calculation(operation: str, operand1: float, operand2: float) -> float:
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
        raise ZeroDivisionError("Division by zero is not allowed.")
    return operand1 / operand2
else:
    raise InvalidOperationException(f"Unsupported operation: {operation}")
