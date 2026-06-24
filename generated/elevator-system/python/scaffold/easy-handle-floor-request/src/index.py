from fastapi import FastAPI
from src.controllers import ElevatorController
from src.database import Base, engine

app = FastAPI()

Base.metadata.create_all(bind=engine)

app.include_router(ElevatorController.router, prefix="/api")
