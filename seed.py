"""Seed database with departments, roles, leave types, and demo users."""

from datetime import date

from config import Config
from models import (
    Department,
    LeaveBalance,
    LeaveType,
    Position,
    Role,
    Unit,
    User,
    db,
)
from services.notifications import ensure_leave_balances


DEPARTMENTS = [
    ("Nursing Directorate", "NUR", "nursing"),
    ("Medical Directorate", "MED", "medical"),
    ("Pharmacy", "PHM", "pharmacy"),
    ("Laboratory", "LAB", "laboratory"),
    ("Radiology", "RAD", "standard"),
    ("Theatre", "THR", "standard"),
    ("Emergency", "EMG", "standard"),
    ("OPD", "OPD", "standard"),
    ("ICU", "ICU", "standard"),
    ("Maternity", "MAT", "standard"),
    ("Pediatrics", "PED", "standard"),
    ("Administration", "ADM", "standard"),
    ("Finance", "FIN", "standard"),
    ("Billing", "BIL", "billing"),
    ("Corporate Affairs", "COR", "corporate"),
    ("Human Resource", "HR", "standard"),
    ("ICT", "ICT", "standard"),
    ("Procurement", "PRO", "standard"),
    ("Stores", "STR", "standard"),
    ("Security", "SEC", "security"),
    ("Maintenance", "MNT", "standard"),
    ("Transport", "TRN", "standard"),
]

STAFF_CATEGORIES = [
    "Nurses", "Doctors", "Pharmacists", "Laboratory Staff", "Radiographers",
    "Physiotherapists", "Midwives", "Theatre Staff", "Nutritionists",
    "Administrators", "Finance", "Billing", "Corporate Affairs",
    "Human Resource", "Procurement", "Records", "Security", "Cleaners",
    "Drivers", "Maintenance", "ICT", "Management",
]

LEAVE_TYPES = [
    ("Annual Leave", "ANN", 21, False, True),
    ("Sick Leave", "SCK", 14, True, True),
    ("Maternity Leave", "MAT", 90, True, True),
    ("Study Leave", "STD", 10, True, True),
    ("Compassionate Leave", "CMP", 5, False, True),
    ("Unpaid Leave", "UNP", 30, False, False),
]

ROLES = [
    ("IT Administrator", "Manage system accounts and settings"),
    ("Employee", "Standard staff member"),
    ("HR Officer", "Final leave approval and HR functions"),
    ("Supervisor", "First-level leave approval"),
]


def seed_database(app):
    with app.app_context():
        db.create_all()
        if Role.query.first():
            print("Database already seeded.")
            return

        for name, desc in ROLES:
            db.session.add(Role(name=name, description=desc))

        for name, code, workflow in DEPARTMENTS:
            db.session.add(Department(name=name, code=code, workflow_type=workflow))

        db.session.flush()

        for lt_name, code, days, doc, paid in LEAVE_TYPES:
            db.session.add(
                LeaveType(
                    name=lt_name,
                    code=code,
                    default_days=days,
                    requires_document=doc,
                    is_paid=paid,
                )
            )

        positions = {}
        for cat in STAFF_CATEGORIES:
            pos = Position(title=f"Staff - {cat}", staff_category=cat)
            db.session.add(pos)
            positions[cat] = pos

        db.session.add(Position(title="Principal Nursing Officer", staff_category="Nurses"))
        db.session.add(Position(title="Deputy Director of Nursing", staff_category="Nurses"))
        db.session.add(Position(title="Head of Department", staff_category="Doctors"))
        db.session.add(Position(title="Medical Director", staff_category="Doctors"))
        db.session.add(Position(title="Laboratory Manager", staff_category="Laboratory Staff"))
        db.session.add(Position(title="Chief Pharmacist", staff_category="Pharmacists"))
        db.session.add(Position(title="Billing Supervisor", staff_category="Billing"))
        db.session.add(Position(title="Corporate Manager", staff_category="Corporate Affairs"))
        db.session.add(Position(title="Security Supervisor", staff_category="Security"))
        db.session.add(Position(title="Finance Manager", staff_category="Finance"))
        db.session.add(Position(title="HR Manager", staff_category="Human Resource"))
        db.session.add(Position(title="IT Officer", staff_category="ICT"))

        db.session.flush()

        nursing = Department.query.filter_by(code="NUR").first()
        medical = Department.query.filter_by(code="MED").first()
        hr_dept = Department.query.filter_by(code="HR").first()
        ict = Department.query.filter_by(code="ICT").first()
        lab = Department.query.filter_by(code="LAB").first()
        billing = Department.query.filter_by(code="BIL").first()

        units = [
            ("General Ward", nursing.id),
            ("Surgical Ward", nursing.id),
            ("Medical Ward", medical.id),
            ("Outpatient", medical.id),
            ("Main Lab", lab.id),
            ("Billing Office", billing.id),
            ("HR Office", hr_dept.id),
            ("IT Department", ict.id),
        ]
        for uname, dept_id in units:
            db.session.add(Unit(name=uname, department_id=dept_id))

        db.session.flush()

        it_role = Role.query.filter_by(name="IT Administrator").first()
        hr_role = Role.query.filter_by(name="HR Officer").first()
        emp_role = Role.query.filter_by(name="Employee").first()
        sup_role = Role.query.filter_by(name="Supervisor").first()

        it_pos = Position.query.filter_by(title="IT Officer").first()
        hr_mgr_pos = Position.query.filter_by(title="HR Manager").first()
        pno_pos = Position.query.filter_by(title="Principal Nursing Officer").first()
        nurse_pos = positions["Nurses"]
        hod_pos = Position.query.filter_by(title="Head of Department").first()
        md_pos = Position.query.filter_by(title="Medical Director").first()
        doc_pos = positions["Doctors"]
        lab_mgr = Position.query.filter_by(title="Laboratory Manager").first()
        lab_staff = positions["Laboratory Staff"]

        it_unit = Unit.query.filter_by(name="IT Department").first()
        hr_unit = Unit.query.filter_by(name="HR Office").first()
        gen_ward = Unit.query.filter_by(name="General Ward").first()
        med_ward = Unit.query.filter_by(name="Medical Ward").first()
        main_lab = Unit.query.filter_by(name="Main Lab").first()

        def create_user(employee_id, staff_number, username, full_name, email, phone,
                        dept_id, unit_id, pos_id, role_id, supervisor_id=None):
            user = User(
                employee_id=employee_id,
                staff_number=staff_number,
                username=username,
                full_name=full_name,
                email=email,
                phone=phone,
                department_id=dept_id,
                unit_id=unit_id,
                position_id=pos_id,
                employment_type="Permanent",
                role_id=role_id,
                supervisor_id=supervisor_id,
                must_change_password=True,
            )
            user.set_password(Config.DEFAULT_PASSWORD)
            db.session.add(user)
            db.session.flush()
            ensure_leave_balances(user)
            return user

        it_admin = create_user(
            "IT001", "SN-IT001", "ITADMIN", "Kwame Asante", "it.admin@ridgehospital.gov.gh",
            "0244000001", ict.id, it_unit.id, it_pos.id, it_role.id,
        )

        hr_officer = create_user(
            "HR001", "SN-HR001", "HROFFICER", "Ama Mensah", "hr@ridgehospital.gov.gh",
            "0244000002", hr_dept.id, hr_unit.id, hr_mgr_pos.id, hr_role.id,
        )

        pno = create_user(
            "NUR001", "SN-NUR001", "PNURSE01", "Michael Bonsu", "m.bonsu@ridgehospital.gov.gh",
            "0244000003", nursing.id, gen_ward.id, pno_pos.id, sup_role.id,
            supervisor_id=hr_officer.id,
        )

        nurse = create_user(
            "NUR1024", "SN-NUR1024", "NUR1024", "Grace Adom", "g.adom@ridgehospital.gov.gh",
            "0244000004", nursing.id, gen_ward.id, nurse_pos.id, emp_role.id,
            supervisor_id=pno.id,
        )

        md = create_user(
            "DOC001", "SN-DOC001", "MEDDIR01", "Dr. Kofi Annan", "k.annan@ridgehospital.gov.gh",
            "0244000005", medical.id, med_ward.id, md_pos.id, sup_role.id,
            supervisor_id=hr_officer.id,
        )

        hod = create_user(
            "DOC002", "SN-DOC002", "HODMED01", "Dr. Efua Boateng", "e.boateng@ridgehospital.gov.gh",
            "0244000006", medical.id, med_ward.id, hod_pos.id, sup_role.id,
            supervisor_id=md.id,
        )

        doctor = create_user(
            "DOC1024", "SN-DOC1024", "DOC1024", "Dr. Samuel Osei", "s.osei@ridgehospital.gov.gh",
            "0244000007", medical.id, med_ward.id, doc_pos.id, emp_role.id,
            supervisor_id=hod.id,
        )

        lab_manager = create_user(
            "LAB001", "SN-LAB001", "LABMGR01", "Patience Akoto", "p.akoto@ridgehospital.gov.gh",
            "0244000008", lab.id, main_lab.id, lab_mgr.id, sup_role.id,
            supervisor_id=hr_officer.id,
        )

        lab_tech = create_user(
            "LAB1024", "SN-LAB1024", "LAB1024", "Eric Tetteh", "e.tetteh@ridgehospital.gov.gh",
            "0244000009", lab.id, main_lab.id, lab_staff.id, emp_role.id,
            supervisor_id=lab_manager.id,
        )

        db.session.commit()
        print("Database seeded successfully!")
        print("\nDemo accounts (default password: Welcome@123):")
        print("  IT Admin:    ITADMIN")
        print("  HR Officer:  HROFFICER")
        print("  Supervisor:  PNURSE01 (Nursing)")
        print("  Nurse:       NUR1024")
        print("  Doctor:      DOC1024")
        print("  Lab Tech:    LAB1024")
