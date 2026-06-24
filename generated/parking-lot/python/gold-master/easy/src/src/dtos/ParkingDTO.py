from pydantic import BaseModel

class ParkVehicleRequest(BaseModel):
    vehicle_id: int

class ParkVehicleResponse(BaseModel):
    ticket_id: int
    vehicle_id: int
    parking_spot_id: int
    entry_time: str
