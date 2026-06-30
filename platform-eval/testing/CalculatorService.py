from src.exceptions.InvalidOperationException import InvalidOperationException

def perform_calculation(operation: str, operand1: float, operand2: float) -> float:
    """Perform a calculation based on the operation type.

    Supported operations: add, subtract, multiply, divide.
    Handle division by zero and invalid operations.
    """
    result = None

    if operation == 'add':
        result = operand1 + operand2
    if operation == 'subtract':
        result = operand1 - operand2
    if operation == 'multiply':
        result = operand1 * operand2
    if operation == 'divide':
        if operand2 == 0:
            raise ZeroDivisionError("Cannot divide by zero")
        result = operand1 / operand2

    if result is None:
        raise InvalidOperationException(f"Unsupported operation: {operation}")

    return result