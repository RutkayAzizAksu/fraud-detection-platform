from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker
import os
import datetime

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost/fraud_db")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Transaction(Base):
    __tablename__ = "transactions"
    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, index=True)
    amount = Column(Float)
    location = Column(String)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    is_fraud = Column(Boolean, default=False)
    fraud_reason = Column(String, nullable=True)

Base.metadata.create_all(bind=engine)
