# Data Dictionary — Smart Hospital Appointment System (Plan B)

All relational tables use **UUID v4** primary keys for internal relational integrity alongside human-readable hospital business identifiers (`CLN-xxx`, `PHY-xxx`, `PAT-xxx`).

## 1. `clinics`
| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | `PRIMARY KEY` | Internal UUID v4 identifier |
| `clinic_code` | `VARCHAR(32)` | `UNIQUE, NOT NULL, INDEX` | Business code (e.g., `CLN-CARDIOLOGY`, `CLN-ORTHO`) |
| `name` | `VARCHAR(120)` | `NOT NULL` | Display name of the outpatient department |
| `created_at` | `TIMESTAMP` | `NOT NULL` | Record creation UTC timestamp |

## 2. `physicians`
| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | `PRIMARY KEY` | Internal UUID v4 identifier |
| `physician_code` | `VARCHAR(32)` | `UNIQUE, NOT NULL, INDEX` | Physician identifier (`PHY-001` .. `PHY-006`) |
| `clinic_id` | `UUID` | `FK -> clinics.id` | Assigned outpatient clinic |
| `full_name` | `VARCHAR(120)` | `NOT NULL` | Physician full name |

## 3. `slots`
| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | `PRIMARY KEY` | Internal UUID v4 identifier |
| `physician_id` | `UUID` | `FK -> physicians.id` | Physician owning the time slot |
| `start_time` | `TIMESTAMP` | `NOT NULL` | Appointment start UTC timestamp |
| `end_time` | `TIMESTAMP` | `NOT NULL` | Appointment end UTC timestamp |
| `status` | `VARCHAR(20)` | `NOT NULL` | `AVAILABLE` or `BOOKED` |
| `version` | `INTEGER` | `NOT NULL, DEFAULT 1` | Row version counter for Optimistic Locking tests |

## 4. `appointments`
| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | `PRIMARY KEY` | Internal UUID v4 identifier |
| `slot_id` | `UUID` | `FK -> slots.id, UNIQUE` | Enforces 1-to-1 booking per slot at schema level |
| `patient_code` | `VARCHAR(32)` | `NOT NULL, INDEX` | Patient business code (`PAT-000123`) |
| `patient_name` | `VARCHAR(120)` | `NOT NULL` | Patient full name |
| `status` | `VARCHAR(20)` | `NOT NULL` | `CONFIRMED` or `CANCELLED` |
| `booked_at` | `TIMESTAMP` | `NOT NULL` | Booking UTC timestamp |

## 5. `visit_history`
| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | `PRIMARY KEY` | Internal UUID v4 identifier |
| `clinic_id` | `UUID` | `FK -> clinics.id, INDEX` | Visited outpatient clinic |
| `patient_code` | `VARCHAR(32)` | `NOT NULL` | Synthetic patient identifier (`PAT-xxxxxx`) |
| `visit_timestamp` | `TIMESTAMP` | `NOT NULL, INDEX` | Historical check-in timestamp |
| `hour_of_day` | `INTEGER` | `NOT NULL` | Extracted hour (`0–23`) for demand baseline aggregation |
| `day_of_week` | `INTEGER` | `NOT NULL` | Day index (`0=Mon .. 6=Sun`) |