from sqlalchemy import Column, Integer, Float, String, create_engine, Base

Base = declarative_base()

class Calculation(Base):
    __tablename__ = 'calculations'

    id = Column(Integer, primary_key=True)
    operand1 = Column(Float, nullable=False)
    operand2 = Column(Float, nullable=False)
    operation = Column(String, nullable=False)
    result = Column(Float, nullable=False)

# Engine and session setup
engine = create_engine('sqlite:///:memory:')
Base.metadata.create_all(engine)
