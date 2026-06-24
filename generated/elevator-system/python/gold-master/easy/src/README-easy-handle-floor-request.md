# Elevator System: Handle Floor Request

## Problem Statement
The elevator system is designed to manage multiple elevators in a building, handling requests from different floors efficiently. The system should ensure that elevators respond to floor requests by adding them to their queue and updating their direction accordingly. This feature is crucial for maintaining an organized and timely response to user requests.

## Requirements
1. Implement the `handle_floor_request` function to add a floor request to the elevator's queue.
2. Update the elevator's direction based on the new request.
3. Handle invalid floor requests by raising an appropriate exception.
4. Ensure that the elevator's state is updated in the database.
5. Consider edge cases such as requests for floors that are already in the queue or invalid floor numbers.

## Instructions
1. Carefully look at `src/dtos/ElevatorDTO.py` for the request/response Pydantic models.
2. Examine `src/models/Elevator.py` to understand the SQLAlchemy ORM schema.
3. Implement the `handle_floor_request` function inside `src/services/ElevatorService.py`.
4. Use the `db: Session` parameter (or the repository in `src/repositories/ElevatorRepository.py`) to interact with the database.
5. Handle errors using FastAPI `HTTPException` — follow the pattern of existing implemented functions.
6. Examine `src/controllers/ElevatorController.py` to understand how the solution will be tested. Your implementation must pass all tests.

## How to Build and Run
1. `pip install -r requirements.txt`
2. `uvicorn src.index:app --reload`
3. `pytest`
