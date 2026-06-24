from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from src.services.ParkingService import ParkingService
from src.dtos.ParkingDTO import ParkVehicleRequest, ParkVehicleResponse
from src.db import get_db

router = APIRouter()

@router.post("/park", response_model=ParkVehicleResponse)
def park_vehicle(request: ParkVehicleRequest, db: Session = Depends(get_db)):
    service = ParkingService(db)
    return service.park_vehicle(request)
