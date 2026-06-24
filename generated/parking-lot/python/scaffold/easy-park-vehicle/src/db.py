from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Create tables
Base.metadata.create_all(bind=engine)

# Seed data
from src.models.ParkingSpot import ParkingSpot
from src.models.Vehicle import Vehicle

def seed_data():
    db = SessionLocal()
    db.add_all([
        ParkingSpot(number=1, is_occupied=False),
        ParkingSpot(number=2, is_occupied=False),
        ParkingSpot(number=3, is_occupied=True),
        Vehicle(license_plate="ABC123", owner_name="John Doe"),
        Vehicle(license_plate="XYZ789", owner_name="Jane Smith")
    ])
    db.commit()
    db.close()

seed_data()
