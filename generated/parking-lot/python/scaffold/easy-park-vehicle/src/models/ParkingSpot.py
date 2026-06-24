from sqlalchemy import Column, Integer, Boolean
from src.db import Base

class ParkingSpot(Base):
    __tablename__ = 'parking_spots'

    id = Column(Integer, primary_key=True, index=True)
    number = Column(Integer, unique=True, index=True)
    is_occupied = Column(Boolean, default=False)
