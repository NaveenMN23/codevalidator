from src.models.Calculation import Calculation

class CalculationRepository:
    @staticmethod
    def save(calculation: Calculation):
        # Here you would normally save to a database
        print(f"Saving calculation: {calculation}")
