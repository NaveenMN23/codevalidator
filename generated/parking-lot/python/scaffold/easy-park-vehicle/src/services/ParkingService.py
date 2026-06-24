from sqlalchemy.orm import Session
from fastapi import HTTPException
from src.repositories.ParkingRepository import ParkingRepository
from src.dtos.ParkingDTO import ParkVehicleRequest, ParkVehicleResponse

class ParkingService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = ParkingRepository(db)

    def park_vehicle(self, request: ParkVehicleRequest) -> ParkVehicleResponse:
        """Assign a vehicle to an available parking spot, create a ticket, and handle errors.

        Steps:
        1. Find an available parking spot — raise HTTPException(404) if none available
        2. Verify the vehicle exists — raise HTTPException(404) if not
        3. Create a ticket for the vehicle
        4. Mark the parking spot as occupied

        Returns: ParkVehicleResponse with ticket details
        """
        # TODO: implement this function
