from fastapi import FastAPI, Depends, HTTPException, status, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import text, func
from pydantic import BaseModel, Field
from datetime import datetime, timedelta
from typing import Optional
import uuid

from database import engine, Base, get_db, Clinic, Physician, Slot, Appointment, VisitHistory
from seed import seed_if_empty

app = FastAPI(title="Smart Hospital Appointment API", version="2.1")

CANCELLATION_WINDOW_HOURS = 2

@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)
    seed_if_empty()

class BookingRequest(BaseModel):
    slot_id: uuid.UUID
    patient_code: str = Field(..., pattern=r"^PAT-\d{3,6}$", examples=["PAT-000123"])
    patient_name: str = Field(..., min_length=2, examples=["Salih Cetin"])

class CancelRequest(BaseModel):
    appointment_id: uuid.UUID
    patient_code: str = Field(..., pattern=r"^PAT-\d{3,6}$", examples=["PAT-000123"])

@app.get("/")
def serve_ui():
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
    now = datetime.utcnow()
    query = (
        db.query(Slot, Physician, Clinic)
        .join(Physician, Slot.physician_id == Physician.id)
        .join(Clinic, Physician.clinic_id == Clinic.id)
        .filter(Slot.status == "AVAILABLE", Slot.start_time > now)
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
    # Pessimistic row-level lock (SELECT ... FOR UPDATE)
    slot = (
        db.query(Slot)
        .filter(Slot.id == req.slot_id)
        .with_for_update()
        .first()
    )
    if not slot:
        raise HTTPException(status_code=404, detail="Slot not found")

    # Kural 1 (FR-3): Geçmiş tarihli slot reddedilir
    if slot.start_time <= datetime.utcnow():
        raise HTTPException(status_code=400, detail="Cannot book a slot in the past")

    # Kural 2 (FR-4 & NFR-2): Aynı hasta veya başka hasta tarafından alınmış slot reddedilir
    existing_appt = db.query(Appointment).filter(Appointment.slot_id == slot.id).first()
    if existing_appt and existing_appt.status == "CONFIRMED":
        if existing_appt.patient_code == req.patient_code:
            raise HTTPException(status_code=409, detail="Patient already booked this slot")
        raise HTTPException(status_code=409, detail="Slot is already booked")

    if slot.status != "AVAILABLE":
        raise HTTPException(status_code=409, detail="Slot is already booked")

    # Önceden iptal edilmiş bir kayıt varsa unique kısıtını korumak için temizle
    if existing_appt and existing_appt.status == "CANCELLED":
        db.delete(existing_appt)
        db.flush()

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

@app.get("/api/v1/appointments")
def list_patient_appointments(
    patient_code: str = Query(..., pattern=r"^PAT-\d{3,6}$"),
    db: Session = Depends(get_db)
):
    rows = (
        db.query(Appointment, Slot, Physician, Clinic)
        .join(Slot, Appointment.slot_id == Slot.id)
        .join(Physician, Slot.physician_id == Physician.id)
        .join(Clinic, Physician.clinic_id == Clinic.id)
        .filter(Appointment.patient_code == patient_code)
        .order_by(Slot.start_time)
        .all()
    )
    return [
        {
            "appointment_id": str(appt.id),
            "slot_id": str(slot.id),
            "patient_code": appt.patient_code,
            "patient_name": appt.patient_name,
            "clinic_code": clinic.clinic_code,
            "physician_name": physician.full_name,
            "start_time": slot.start_time.isoformat(),
            "status": appt.status,
            "booked_at": appt.booked_at.isoformat() + "Z"
        }
        for appt, slot, physician, clinic in rows
    ]

@app.post("/api/v1/cancel")
def cancel_appointment(req: CancelRequest, db: Session = Depends(get_db)):
    appt = (
        db.query(Appointment)
        .filter(
            Appointment.id == req.appointment_id,
            Appointment.patient_code == req.patient_code
        )
        .with_for_update()
        .first()
    )
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found for this patient")
    if appt.status == "CANCELLED":
        raise HTTPException(status_code=400, detail="Appointment is already cancelled")

    slot = db.query(Slot).filter(Slot.id == appt.slot_id).with_for_update().first()
    if not slot:
        raise HTTPException(status_code=404, detail="Associated slot not found")

    # Kural 3 (FR-6): İptal zaman penceresi kontrolü (en az 2 saat önce)
    cutoff = slot.start_time - timedelta(hours=CANCELLATION_WINDOW_HOURS)
    if datetime.utcnow() > cutoff:
        raise HTTPException(
            status_code=400,
            detail=f"Cancellation window closed (must cancel at least {CANCELLATION_WINDOW_HOURS} hours before slot)"
        )

    appt.status = "CANCELLED"
    slot.status = "AVAILABLE"
    slot.version += 1
    db.commit()

    return {
        "appointment_id": str(appt.id),
        "slot_id": str(slot.id),
        "status": appt.status,
        "slot_status": slot.status
    }

@app.get("/api/v1/analytics/demand")
def get_demand_baseline(clinic_code: Optional[str] = None, db: Session = Depends(get_db)):
    query = (
        db.query(
            Clinic.clinic_code,
            VisitHistory.hour_of_day,
            func.count(VisitHistory.id).label("visit_count")
        )
        .join(Clinic, VisitHistory.clinic_id == Clinic.id)
    )
    if clinic_code:
        query = query.filter(Clinic.clinic_code == clinic_code)

    rows = (
        query.group_by(Clinic.clinic_code, VisitHistory.hour_of_day)
        .order_by(Clinic.clinic_code, VisitHistory.hour_of_day)
        .all()
    )
    return [
        {
            "clinic_code": r.clinic_code,
            "hour_of_day": r.hour_of_day,
            "visit_count": r.visit_count
        }
        for r in rows
    ]