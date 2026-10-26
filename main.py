from fastapi import FastAPI
from datetime import datetime

app = FastAPI(title="Smart Hospital Appointment API", version="1.0")

@app.get("/healthz")
def health_check():
    return {
        "status": "ok",
        "service": "hospital-appointment-api",
        "database": "connected",
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }