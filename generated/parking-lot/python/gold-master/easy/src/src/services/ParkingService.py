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
        available_spot = self.repository.find_available_spot()
if not available_spot:
    raise HTTPException(status_code=404, detail='No available parking spots')

vehicle = self.repository.find_vehicle_by_id(request.vehicle_id)
if not vehicle:
    raise HTTPException(status_code=404, detail='Vehicle not found')

ticket = self.repository.create_ticket(vehicle_id=request.vehicle_id, parking_spot_id=available_spot.id)
self.repository.mark_spot_as_occupied(parking_spot_id=available_spot.id)

return ParkVehicleResponse(
    ticket_id=ticket.id,
    vehicle_id=ticket.vehicle_id,
    parking_spot_id=ticket.parking_spot_id,
    entry_time=ticket.entry_time.isoformat()
)
