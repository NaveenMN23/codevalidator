from fastapi import FastAPI
from src.controllers.CalculatorController import router as calculator_router

app = FastAPI()

app.include_router(calculator_router, prefix="/calculator")

@app.get("/")
def read_root():
    return {"message": "Welcome to the Calculator API"}
