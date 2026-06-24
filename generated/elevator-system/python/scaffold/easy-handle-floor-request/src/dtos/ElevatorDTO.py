from pydantic import BaseModel

class FloorRequestDTO(BaseModel):
    floor_number: int
    direction: str  # 'up' or 'down'
