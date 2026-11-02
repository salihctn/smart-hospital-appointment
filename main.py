from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional
import uuid

from database import engine, Base, get_db, Clinic, Physician, Slot, Appointment
from seed import seed_if_empty

app = FastAPI(title="Smart Hospital Appointment API", version="2.0")

@app.on_event("startup")
def on_startup():
    # Tabloları ve indeksleri oluştur (Schema Migration)
    Base.metadata.create_all(bind=engine)
    # Tablolar boşsa sentetik verileri yükle
    seed_if_empty()

class BookingRequest(BaseModel):
    slot_id: uuid.UUID
    patient_code: str = Field(..., pattern=r"^PAT-\d{3,6}$", examples=["PAT-000123"])
    patient_name: str = Field(..., min_length=2, examples=["Salih Cetin"])

@app.get("/")
def serve_walking_skeleton_ui():
    return FileResponse("index.html")

@app.get("/healthz")
def health_check(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {
        "status": "ok",
        "service": "hospital-appointment-api",
        "database": "connected",
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }

@app.get("/api/v1/clinics")
def list_clinics(db: Session = Depends(get_db)):
    clinics = db.query(Clinic).order_by(Clinic.clinic_code).all()
    return [
        {"id": str(c.id), "clinic_code": c.clinic_code, "name": c.name}
        for c in clinics
    ]

@app.get("/api/v1/slots")
def list_available_slots(clinic_code: Optional[str] = None, db: Session = Depends(get_db)):
    query = (
        db.query(Slot, Physician, Clinic)
        .join(Physician, Slot.physician_id == Physician.id)
        .join(Clinic, Physician.clinic_id == Clinic.id)
        .filter(Slot.status == "AVAILABLE")
    )
    if clinic_code:
        query = query.filter(Clinic.clinic_code == clinic_code)

    results = query.order_by(Slot.start_time).all()
    return [
        {
            "slot_id": str(slot.id),
            "clinic_code": clinic.clinic_code,
            "clinic_name": clinic.name,
            "physician_code": physician.physician_code,
            "physician_name": physician.full_name,
            "start_time": slot.start_time.isoformat(),
            "end_time": slot.end_time.isoformat(),
            "status": slot.status,
            "version": slot.version
        }
        for slot, physician, clinic in results
    ]

@app.post("/api/v1/book", status_code=status.HTTP_201_CREATED)
def book_slot(req: BookingRequest, db: Session = Depends(get_db)):
    # Pessimistic row-level lock ile aynı slota çift randevuyu (NFR-2) engeller
    slot = (
        db.query(Slot)
        .filter(Slot.id == req.slot_id)
        .with_for_update()
        .first()
    )
    if not slot:
        raise HTTPException(status_code=404, detail="Slot not found")
    if slot.status != "AVAILABLE":
        raise HTTPException(status_code=409, detail="Slot is already booked")

    slot.status = "BOOKED"
    slot.version += 1

    appointment = Appointment(
        slot_id=slot.id,
        patient_code=req.patient_code,
        patient_name=req.patient_name,
        status="CONFIRMED"
    )
    db.add(appointment)
    db.commit()
    db.refresh(appointment)

    return {
        "appointment_id": str(appointment.id),
        "slot_id": str(slot.id),
        "patient_code": appointment.patient_code,
        "patient_name": appointment.patient_name,
        "status": appointment.status,
        "booked_at": appointment.booked_at.isoformat() + "Z"
    }