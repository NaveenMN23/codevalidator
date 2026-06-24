from sqlalchemy import Column, Integer, String, Boolean
from src.database import Base

class Elevator(Base):
    __tablename__ = 'elevators'

    id = Column(Integer, primary_key=True, index=True)
    current_floor = Column(Integer, default=0)
    target_floors = Column(String, default="")  # Comma-separated list of floors
    direction = Column(String, default="idle")  # 'up', 'down', 'idle'
    is_moving = Column(Boolean, default=False)
