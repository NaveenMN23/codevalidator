from fastapi import FastAPI
from src.controllers.ParkingController import router as parking_router

app = FastAPI()

app.include_router(parking_router, prefix="/api")
