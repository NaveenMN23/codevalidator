from sqlalchemy import Column, Integer, String
from src.db import Base

class Vehicle(Base):
    __tablename__ = 'vehicles'

    id = Column(Integer, primary_key=True, index=True)
    license_plate = Column(String, unique=True, index=True)
    owner_name = Column(String)
