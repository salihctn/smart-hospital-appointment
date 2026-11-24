import urllib.request
import urllib.error
import json
from concurrent.futures import ThreadPoolExecutor

BASE = "http://localhost:8000"

def req(method, path, payload=None):
    data = json.dumps(payload).encode("utf-8") if payload else None
    headers = {"Content-Type": "application/json"} if payload else {}
    r = urllib.request.Request(f"{BASE}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())

print("1. Health Check:", req("GET", "/healthz")[0])
code, slots = req("GET", "/api/v1/slots?clinic_code=CLN-CARDIOLOGY")
print(f"2. FR-1 Slots Filter: HTTP {code}, count={len(slots)}")

# FR-2 & FR-4: Book and Duplicate check
slot1 = slots[0]["slot_id"]
c1, b1 = req("POST", "/api/v1/book", {"slot_id": slot1, "patient_code": "PAT-111111", "patient_name": "Test User"})
c2, b2 = req("POST", "/api/v1/book", {"slot_id": slot1, "patient_code": "PAT-111111", "patient_name": "Test User"})
print(f"3. FR-2 Book: HTTP {c1} | FR-4 Duplicate Reject: HTTP {c2} ({b2.get('detail')})")

# FR-5: My Appointments
c3, appts = req("GET", "/api/v1/appointments?patient_code=PAT-111111")
print(f"4. FR-5 My Appointments: HTTP {c3}, found={len(appts)}")

# FR-6: Cancel
c4, canc = req("POST", "/api/v1/cancel", {"appointment_id": b1["appointment_id"], "patient_code": "PAT-111111"})
print(f"5. FR-6 Cancel: HTTP {c4}, slot_status={canc.get('slot_status')}")

# FR-7: Demand Analytics
c5, dem = req("GET", "/api/v1/analytics/demand")
print(f"6. FR-7 Demand Analytics: HTTP {c5}, rows={len(dem)}")

# NFR-2: 20 Concurrent Bookings on same slot
slot2 = slots[1]["slot_id"]
def attempt(i):
    return req("POST", "/api/v1/book", {"slot_id": slot2, "patient_code": f"PAT-2000{i:02d}", "patient_name": f"User {i}"})[0]

with ThreadPoolExecutor(max_workers=20) as ex:
    statuses = list(ex.map(attempt, range(20)))
print(f"7. NFR-2 Concurrency (20 users -> 1 slot): 201 count={statuses.count(201)}, 409 count={statuses.count(409)}")