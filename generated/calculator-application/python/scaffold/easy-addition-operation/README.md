# Calculator: Implement Addition Operation

## Problem Statement
The calculator application is designed to perform basic arithmetic operations. Users can perform operations such as addition, subtraction, multiplication, and division. This specific feature involves implementing the addition operation, where users can add two numbers and receive the result.

## Requirements
1. Implement the `add` function in `src/services/CalculatorService.py` to perform the addition of two numbers.
2. The function should accept two operands as input and return their sum.
3. Handle invalid inputs by raising a `ValueError` if the inputs are not numbers.
4. Store the result of the addition in the repository.
5. Ensure the application returns a proper response with the result of the addition.

## Instructions
1. Carefully look at `src/dtos/CalculationDTO.py` for the request/response Pydantic models.
2. Examine `src/models/Calculation.py` to understand the SQLAlchemy ORM schema.
3. Implement the `add` function inside `src/services/CalculatorService.py`.
4. Use the `CalculationRepository` to store the result.
5. Handle errors using FastAPI `HTTPException` — follow the pattern of existing implemented functions.
6. Examine `src/controllers/CalculatorController.py` to understand how the solution will be tested. Your implementation must pass all tests.

## How to Build and Run
1. `pip install -r requirements.txt`
2. `uvicorn src.index:app --reload`
3. `pytest`
