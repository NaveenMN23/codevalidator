# Calculator: Perform a Calculation

## Problem Statement
The calculator application is designed to perform basic arithmetic operations such as addition, subtraction, multiplication, and division. Users can input two operands and specify the operation they wish to perform. The system should execute the operation and return the result. This feature is crucial for users who need quick and reliable calculations.

## Requirements
1. Implement the `perform_calculation()` function to handle basic arithmetic operations: addition, subtraction, multiplication, and division.
2. The function should accept an operation type and two operands as input.
3. Handle division by zero by raising a `ZeroDivisionError`.
4. Raise an `InvalidOperationException` for unsupported operations.
5. Ensure the function returns the correct result for valid operations.

## Instructions
1. Carefully look at `src/dtos/CalculationDTO.py` for the request/response Pydantic models.
2. Examine `src/models/Calculation.py` to understand the SQLAlchemy ORM schema.
3. Implement the `perform_calculation` function inside `src/services/CalculatorService.py`.
4. Use the `db: Session` parameter (or the repository in `src/repositories/CalculationRepository.py`) to interact with the database.
5. Handle errors using FastAPI `HTTPException` — follow the pattern of existing implemented functions.
6. Examine `src/controllers/CalculatorController.py` to understand how the solution will be tested. Your implementation must pass all tests.

## How to Build and Run
1. `pip install -r requirements.txt`
2. `uvicorn src.index:app --reload`
3. `pytest`
