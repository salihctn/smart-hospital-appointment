import random
from datetime import datetime, timedelta
from database import SessionLocal, Clinic, Physician, Slot, VisitHistory

def seed_if_empty():
    db = SessionLocal()
    try:
        if db.query(Clinic).count() > 0:
            return

        random.seed(42)

        clinics_data = [
            Clinic(clinic_code="CLN-CARDIOLOGY", name="Cardiology Outpatient Clinic"),
            Clinic(clinic_code="CLN-ORTHO", name="Orthopedics and Traumatology"),
            Clinic(clinic_code="CLN-NEURO", name="Neurology Outpatient Clinic"),
        ]
        db.add_all(clinics_data)
        db.flush()

        physicians_data = [
            Physician(physician_code="PHY-001", clinic_id=clinics_data[0].id, full_name="Dr. Ahmet Yilmaz"),
            Physician(physician_code="PHY-002", clinic_id=clinics_data[0].id, full_name="Dr. Elif Kaya"),
            Physician(physician_code="PHY-003", clinic_id=clinics_data[1].id, full_name="Dr. Mehmet Demir"),
            Physician(physician_code="PHY-004", clinic_id=clinics_data[1].id, full_name="Dr. Zeynep Celik"),
            Physician(physician_code="PHY-005", clinic_id=clinics_data[2].id, full_name="Dr. Caner Aydin"),
            Physician(physician_code="PHY-006", clinic_id=clinics_data[2].id, full_name="Dr. Selin Arslan"),
        ]
        db.add_all(physicians_data)
        db.flush()

        # Önümüzdeki 3 gün için 30 dakikalık randevu slotları oluştur
        base_day = (datetime.utcnow() + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
        slots_to_add = []
        for day_offset in range(3):
            current_day = base_day + timedelta(days=day_offset)
            for phys in physicians_data:
                for hour in [9, 10, 11, 14, 15]:
                    for minute in [0, 30]:
                        start_dt = current_day.replace(hour=hour, minute=minute)
                        end_dt = start_dt + timedelta(minutes=30)
                        slots_to_add.append(
                            Slot(
                                physician_id=phys.id,
                                start_time=start_dt,
                                end_time=end_dt,
                                status="AVAILABLE",
                                version=1
                            )
                        )
        db.add_all(slots_to_add)

        # Son 14 gün için gerçekçi sabah yoğunluğunu (09:00-11:00 peak) yansıtan sentetik ziyaret geçmişi
        weighted_hours = [9, 9, 9, 10, 10, 10, 11, 11, 13, 14, 14, 15, 16]
        history_records = []
        now = datetime.utcnow()
        for days_ago in range(1, 15):
            visit_day = now - timedelta(days=days_ago)
            if visit_day.weekday() >= 5:
                continue
            for clinic in clinics_data:
                daily_visits = random.randint(18, 30)
                for _ in range(daily_visits):
                    hr = random.choice(weighted_hours)
                    mn = random.choice([0, 15, 30, 45])
                    ts = visit_day.replace(hour=hr, minute=mn, second=0, microsecond=0)
                    pat_code = f"PAT-{random.randint(100000, 999999)}"
                    history_records.append(
                        VisitHistory(
                            clinic_id=clinic.id,
                            patient_code=pat_code,
                            visit_timestamp=ts,
                            hour_of_day=hr,
                            day_of_week=ts.weekday()
                        )
                    )
        db.add_all(history_records)
        db.commit()
    finally:
        db.close()