from sqlalchemy import Column, Integer, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from src.db import Base
from datetime import datetime

class Ticket(Base):
    __tablename__ = 'tickets'

    id = Column(Integer, primary_key=True, index=True)
    vehicle_id = Column(Integer, ForeignKey('vehicles.id'))
    parking_spot_id = Column(Integer, ForeignKey('parking_spots.id'))
    entry_time = Column(DateTime, default=datetime.utcnow)
    exit_time = Column(DateTime, nullable=True)

    vehicle = relationship("Vehicle")
    parking_spot = relationship("ParkingSpot")
