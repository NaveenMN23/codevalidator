from sqlalchemy.orm import Session
from src.repositories.ElevatorRepository import ElevatorRepository
from src.dtos.ElevatorDTO import FloorRequestDTO
from src.exceptions.InvalidFloorException import InvalidFloorException

class ElevatorService:
    def __init__(self):
        self.elevator_repository = ElevatorRepository()

    def handle_floor_request(self, request: FloorRequestDTO, db: Session):
        """Add floor request to queue, update elevator direction, handle invalid floor requests"""
        elevator = self.elevator_repository.get_elevator_by_id(request.elevator_id, db)
if not elevator:
    raise InvalidFloorException("Elevator not found")

if request.floor_number < 0 or request.floor_number > 100:  # Assuming building has floors 0 to 100
    raise InvalidFloorException("Invalid floor number")

if str(request.floor_number) in elevator.target_floors.split(','):
    return  # Floor already in queue, no need to add again

elevator.target_floors += f',{request.floor_number}' if elevator.target_floors else str(request.floor_number)

if elevator.current_floor < request.floor_number:
    elevator.direction = 'up'
elif elevator.current_floor > request.floor_number:
    elevator.direction = 'down'
else:
    elevator.direction = 'idle'

elevator.is_moving = True

self.elevator_repository.update_elevator(elevator, db)
return {'message': 'Floor request added successfully'}

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
