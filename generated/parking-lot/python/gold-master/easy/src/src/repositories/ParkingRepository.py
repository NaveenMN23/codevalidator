from sqlalchemy.orm import Session
from src.models.ParkingSpot import ParkingSpot
from src.models.Vehicle import Vehicle
from src.models.Ticket import Ticket

class ParkingRepository:
    def __init__(self, db: Session):
        self.db = db

    def find_available_spot(self):
        return self.db.query(ParkingSpot).filter_by(is_occupied=False).first()

    def find_vehicle_by_id(self, vehicle_id: int):
        return self.db.query(Vehicle).filter_by(id=vehicle_id).first()

    def create_ticket(self, vehicle_id: int, parking_spot_id: int):
        ticket = Ticket(vehicle_id=vehicle_id, parking_spot_id=parking_spot_id)
        self.db.add(ticket)
        self.db.commit()
        return ticket

    def mark_spot_as_occupied(self, parking_spot_id: int):
        spot = self.db.query(ParkingSpot).filter_by(id=parking_spot_id).first()
        if spot:
            spot.is_occupied = True
            self.db.commit()
