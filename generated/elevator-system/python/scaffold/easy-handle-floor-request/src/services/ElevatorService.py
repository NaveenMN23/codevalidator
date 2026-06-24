from sqlalchemy.orm import Session
from src.repositories.ElevatorRepository import ElevatorRepository
from src.dtos.ElevatorDTO import FloorRequestDTO
from src.exceptions.InvalidFloorException import InvalidFloorException

class ElevatorService:
    def __init__(self):
        self.elevator_repository = ElevatorRepository()

    def handle_floor_request(self, request: FloorRequestDTO, db: Session):
        """Add floor request to queue, update elevator direction, handle invalid floor requests"""
        # TODO: implement this function

    def get_elevator_status(self, elevator_id: int, db: Session):
        elevator = self.elevator_repository.get_elevator_by_id(elevator_id, db)
        if not elevator:
            raise InvalidFloorException("Elevator not found")
        return {
            "id": elevator.id,
            "current_floor": elevator.current_floor,
            "target_floors": elevator.target_floors,
            "direction": elevator.direction,
            "is_moving": elevator.is_moving
        }
