# Ridge Leave Management System

Hospital-grade leave management for Ridge Hospital.

## Quick Start

```bash
pip install -r requirements.txt
python app.py
```

Open http://localhost:5000

## Demo Accounts

Default password for all accounts: `Welcome@123` (must change on first login)

| Role | Username |
|------|----------|
| IT Administrator | ITADMIN |
| HR Officer | HROFFICER |
| Nursing Supervisor | PNURSE01 |
| Nurse | NUR1024 |
| Doctor | DOC1024 |
| Lab Technician | LAB1024 |

## Stack

- **Backend:** Python / Flask / SQLAlchemy
- **Frontend:** HTML / CSS / JavaScript
- **Database:** SQLite (dev)

## Workflow

Employee → Supervisor → HR → Approved (Doctors: Supervisor → Medical Director → HR)
