class InvalidOperationException(Exception):
    def __init__(self, operation: str):
        super().__init__(f"Invalid operation: {operation}")
