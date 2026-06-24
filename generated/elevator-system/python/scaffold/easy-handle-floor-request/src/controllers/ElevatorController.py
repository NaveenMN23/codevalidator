from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from src.services.ElevatorService import ElevatorService
from src.dtos.ElevatorDTO import FloorRequestDTO
from src.database import get_db

router = APIRouter()

elevator_service = ElevatorService()

@router.post("/elevator/request")
def handle_floor_request(request: FloorRequestDTO, db: Session = Depends(get_db)):
    try:
        return elevator_service.handle_floor_request(request, db)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/elevator/status/{elevator_id}")
def get_elevator_status(elevator_id: int, db: Session = Depends(get_db)):
    return elevator_service.get_elevator_status(elevator_id, db)
