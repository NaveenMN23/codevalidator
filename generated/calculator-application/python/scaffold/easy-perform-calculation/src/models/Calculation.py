from sqlalchemy import Column, Integer, String, Float
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class Calculation(Base):
    __tablename__ = 'calculations'

    id = Column(Integer, primary_key=True, index=True)
    operation = Column(String, index=True)
    operand1 = Column(Float)
    operand2 = Column(Float)
    result = Column(Float)
