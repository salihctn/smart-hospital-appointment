import os
import uuid
from datetime import datetime
from sqlalchemy import (
    create_engine, Column, String, Integer, DateTime, ForeignKey, Index
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://admin:adminpassword@localhost:5432/hospital_db"
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Clinic(Base):
    __tablename__ = "clinics"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    clinic_code = Column(String(32), unique=True, nullable=False, index=True)
    name = Column(String(120), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    physicians = relationship("Physician", back_populates="clinic")

class Physician(Base):
    __tablename__ = "physicians"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    physician_code = Column(String(32), unique=True, nullable=False, index=True)
    clinic_id = Column(UUID(as_uuid=True), ForeignKey("clinics.id", ondelete="CASCADE"), nullable=False)
    full_name = Column(String(120), nullable=False)

    clinic = relationship("Clinic", back_populates="physicians")
    slots = relationship("Slot", back_populates="physician")

class Slot(Base):
    __tablename__ = "slots"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    physician_id = Column(UUID(as_uuid=True), ForeignKey("physicians.id", ondelete="CASCADE"), nullable=False)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    status = Column(String(20), default="AVAILABLE", nullable=False)
    version = Column(Integer, default=1, nullable=False)  # Optimistic locking support

    physician = relationship("Physician", back_populates="slots")
    appointment = relationship("Appointment", back_populates="slot", uselist=False)

    __table_args__ = (
        Index("ix_slots_physician_start_status", "physician_id", "start_time", "status"),
    )

class Appointment(Base):
    __tablename__ = "appointments"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slot_id = Column(UUID(as_uuid=True), ForeignKey("slots.id", ondelete="RESTRICT"), unique=True, nullable=False)
    patient_code = Column(String(32), nullable=False, index=True)
    patient_name = Column(String(120), nullable=False)
    status = Column(String(20), default="CONFIRMED", nullable=False)
    booked_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    slot = relationship("Slot", back_populates="appointment")

class VisitHistory(Base):
    __tablename__ = "visit_history"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    clinic_id = Column(UUID(as_uuid=True), ForeignKey("clinics.id", ondelete="CASCADE"), nullable=False, index=True)
    patient_code = Column(String(32), nullable=False)
    visit_timestamp = Column(DateTime, nullable=False, index=True)
    hour_of_day = Column(Integer, nullable=False)
    day_of_week = Column(Integer, nullable=False)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()