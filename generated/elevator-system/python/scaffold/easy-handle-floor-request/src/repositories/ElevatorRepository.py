from sqlalchemy.orm import Session
from src.models.Elevator import Elevator

class ElevatorRepository:
    def get_elevator_by_id(self, elevator_id: int, db: Session) -> Elevator:
        return db.query(Elevator).filter(Elevator.id == elevator_id).first()

    def update_elevator(self, elevator: Elevator, db: Session):
        db.add(elevator)
        db.commit()
        db.refresh(elevator)
