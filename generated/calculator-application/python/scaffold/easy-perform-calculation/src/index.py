from fastapi import FastAPI
from src.controllers.CalculatorController import router as calculator_router

app = FastAPI()

app.include_router(calculator_router)
