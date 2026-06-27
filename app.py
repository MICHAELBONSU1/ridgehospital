import os
import uuid
from datetime import date, datetime, timezone
from functools import wraps

from flask import Flask, jsonify, redirect, render_template, request, session, url_for
from flask_login import LoginManager, current_user, login_required, login_user, logout_user
from werkzeug.utils import secure_filename

from config import Config
from models import (
    Attachment,
    AuditLog,
    Department,
    LeaveBalance,
    LeaveRequest,
    LeaveType,
    LoginHistory,
    Notification,
    Position,
    Role,
    Unit,
    User,
    db,
)
from seed import seed_database
from services.leave_service import (
    calculate_days,
    cancel_leave_request,
    change_password,
    get_pending_for_approver,
    log_audit,
    log_login,
    process_approval,
    submit_leave_request,
)
from services.notifications import check_unit_conflict, ensure_leave_balances

app = Flask(__name__)
app.config.from_object(Config)
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


def role_required(*roles):
    def decorator(f):
        @wraps(f)
        @login_required
        def wrapped(*args, **kwargs):
            if current_user.role.name not in roles:
                return jsonify({"error": "Unauthorized"}), 403
            return f(*args, **kwargs)
        return wrapped
    return decorator


def get_dashboard_redirect(user):
    role = user.role.name
    if role == "IT Administrator":
        return url_for("it_dashboard")
    if role == "HR Officer":
        return url_for("hr_dashboard")
    if role == "Supervisor":
        return url_for("supervisor_dashboard")
    return url_for("employee_dashboard")


# ── Page Routes ──────────────────────────────────────────────

@app.route("/")
def splash():
    if current_user.is_authenticated:
        if current_user.must_change_password:
            return redirect(url_for("change_password_page"))
        return redirect(get_dashboard_redirect(current_user))
    return render_template("splash.html")


@app.route("/home")
def index():
    return redirect(url_for("splash"))


@app.route("/login")
def login():
    if current_user.is_authenticated:
        if current_user.must_change_password:
            return redirect(url_for("change_password_page"))
        return redirect(get_dashboard_redirect(current_user))
    return render_template("login.html")


@app.route("/change-password")
@login_required
def change_password_page():
    return render_template("change_password.html")


@app.route("/employee/dashboard")
@login_required
def employee_dashboard():
    return render_template("employee/dashboard.html")


@app.route("/supervisor/dashboard")
@login_required
def supervisor_dashboard():
    return render_template("supervisor/dashboard.html")


@app.route("/hr/dashboard")
@login_required
def hr_dashboard():
    return render_template("hr/dashboard.html")


@app.route("/it/dashboard")
@login_required
def it_dashboard():
    return render_template("it/dashboard.html")


# ── Auth API ─────────────────────────────────────────────────

@app.route("/api/auth/login", methods=["POST"])
def api_login():
    data = request.get_json() or {}
    username = data.get("username", "").strip()
    password = data.get("password", "")

    user = User.query.filter_by(username=username).first()
    if not user or not user.check_password(password):
        log_login(None, username, False)
        db.session.commit()
        return jsonify({"error": "Invalid username or password."}), 401

    if user.is_locked:
        log_login(user.id, username, False)
        db.session.commit()
        return jsonify({"error": "Account is locked. Contact IT."}), 403

    if not user.is_active:
        return jsonify({"error": "Account is deactivated."}), 403

    login_user(user)
    log_login(user.id, username, True)
    log_audit(user.id, "login", f"User {username} logged in")
    db.session.commit()

    return jsonify({
        "message": "Login successful",
        "must_change_password": user.must_change_password,
        "redirect": "/change-password" if user.must_change_password else get_dashboard_redirect(user),
        "user": user.to_dict(),
    })


@app.route("/api/auth/logout", methods=["POST"])
@login_required
def api_logout():
    log_audit(current_user.id, "logout", "User logged out")
    db.session.commit()
    logout_user()
    return jsonify({"message": "Logged out"})


@app.route("/api/auth/change-password", methods=["POST"])
@login_required
def api_change_password():
    data = request.get_json() or {}
    old_password = data.get("old_password", "")
    new_password = data.get("new_password", "")

    if len(new_password) < 8:
        return jsonify({"error": "Password must be at least 8 characters."}), 400

    success, message = change_password(current_user, new_password, old_password)
    if not success:
        return jsonify({"error": message}), 400

    db.session.commit()
    return jsonify({
        "message": message,
        "redirect": get_dashboard_redirect(current_user),
    })


@app.route("/api/auth/me")
@login_required
def api_me():
    return jsonify({"user": current_user.to_dict()})


# ── Notifications API ────────────────────────────────────────

@app.route("/api/notifications")
@login_required
def api_notifications():
    notifs = Notification.query.filter_by(user_id=current_user.id).order_by(
        Notification.created_at.desc()
    ).limit(20).all()
    unread = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
    return jsonify({"notifications": [n.to_dict() for n in notifs], "unread_count": unread})


@app.route("/api/notifications/<int:nid>/read", methods=["POST"])
@login_required
def api_mark_read(nid):
    notif = Notification.query.filter_by(id=nid, user_id=current_user.id).first_or_404()
    notif.is_read = True
    db.session.commit()
    return jsonify({"message": "Marked as read"})


@app.route("/api/notifications/read-all", methods=["POST"])
@login_required
def api_mark_all_read():
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update({"is_read": True})
    db.session.commit()
    return jsonify({"message": "All marked as read"})


# ── Employee API ─────────────────────────────────────────────

@app.route("/api/employee/dashboard")
@login_required
def api_employee_dashboard():
    user = current_user
    today = date.today()
    balances = LeaveBalance.query.filter_by(user_id=user.id, year=today.year).all()
    requests = LeaveRequest.query.filter_by(employee_id=user.id).order_by(
        LeaveRequest.created_at.desc()
    ).all()

    pending = [r for r in requests if "pending" in r.status or r.status == "more_info_requested"]
    approved = [r for r in requests if r.status in ("completed", "hr_approved")]
    rejected = [r for r in requests if "rejected" in r.status]
    upcoming = [
        r for r in requests
        if r.status == "completed" and r.start_date >= today
    ]

    return jsonify({
        "user": user.to_dict(),
        "leave_balances": [
            {
                "leave_type": b.leave_type.name,
                "total": b.total_days,
                "used": b.used_days,
                "pending": b.pending_days,
                "remaining": b.remaining_days,
            }
            for b in balances
        ],
        "pending_leave": [r.to_dict() for r in pending],
        "approved_leave": [r.to_dict() for r in approved],
        "rejected_leave": [r.to_dict() for r in rejected],
        "upcoming_leave": [r.to_dict() for r in upcoming],
    })


@app.route("/api/employee/leave", methods=["POST"])
@login_required
def api_apply_leave():
    data = request.get_json() or {}
    leave_type_id = data.get("leave_type_id")
    start_date = data.get("start_date")
    end_date = data.get("end_date")
    reason = data.get("reason", "")
    submit = data.get("submit", False)

    if not all([leave_type_id, start_date, end_date]):
        return jsonify({"error": "Missing required fields."}), 400

    days = calculate_days(start_date, end_date)
    if days <= 0:
        return jsonify({"error": "Invalid date range."}), 400

    leave_req = LeaveRequest(
        employee_id=current_user.id,
        leave_type_id=leave_type_id,
        start_date=date.fromisoformat(start_date),
        end_date=date.fromisoformat(end_date),
        days_requested=days,
        reason=reason,
        status="draft",
        current_stage="draft",
    )
    db.session.add(leave_req)
    db.session.flush()

    if submit:
        submit_leave_request(leave_req)

    db.session.commit()
    return jsonify({"message": "Leave request saved.", "request": leave_req.to_dict()})


@app.route("/api/employee/leave/<int:rid>/submit", methods=["POST"])
@login_required
def api_submit_leave(rid):
    leave_req = LeaveRequest.query.filter_by(id=rid, employee_id=current_user.id).first_or_404()
    if leave_req.status != "draft":
        return jsonify({"error": "Only draft requests can be submitted."}), 400
    submit_leave_request(leave_req)
    db.session.commit()
    return jsonify({"message": "Leave submitted.", "request": leave_req.to_dict()})


@app.route("/api/employee/leave/<int:rid>/cancel", methods=["POST"])
@login_required
def api_cancel_leave(rid):
    leave_req = LeaveRequest.query.filter_by(id=rid, employee_id=current_user.id).first_or_404()
    if not cancel_leave_request(leave_req):
        return jsonify({"error": "Cannot cancel this request."}), 400
    db.session.commit()
    return jsonify({"message": "Leave cancelled."})


@app.route("/api/employee/profile", methods=["PUT"])
@login_required
def api_update_profile():
    data = request.get_json() or {}
    if "phone" in data:
        current_user.phone = data["phone"]
    if "email" in data:
        existing = User.query.filter(User.email == data["email"], User.id != current_user.id).first()
        if existing:
            return jsonify({"error": "Email already in use."}), 400
        current_user.email = data["email"]
    log_audit(current_user.id, "profile_updated", "Employee updated profile")
    db.session.commit()
    return jsonify({"message": "Profile updated.", "user": current_user.to_dict()})


@app.route("/api/leave-types")
@login_required
def api_leave_types():
    types = LeaveType.query.all()
    return jsonify({"leave_types": [
        {"id": t.id, "name": t.name, "code": t.code, "requires_document": t.requires_document}
        for t in types
    ]})


# ── Supervisor API ───────────────────────────────────────────

@app.route("/api/supervisor/dashboard")
@login_required
def api_supervisor_dashboard():
    today = date.today()
    pending = get_pending_for_approver(current_user, "supervisor")
    medical_pending = get_pending_for_approver(current_user, "medical_director")

    all_pending = pending + medical_pending
    subordinate_ids = [s.id for s in current_user.subordinates]

    all_team_requests = LeaveRequest.query.filter(
        LeaveRequest.employee_id.in_(subordinate_ids)
    ).order_by(LeaveRequest.created_at.desc()).all() if subordinate_ids else []

    today_requests = [r for r in all_team_requests if r.created_at and r.created_at.date() == today]
    approved = [r for r in all_team_requests if r.status in ("completed", "hr_approved", "supervisor_approved", "medical_director_approved", "hr_pending")]
    rejected = [r for r in all_team_requests if "rejected" in r.status]

    upcoming_team = [
        r for r in all_team_requests
        if r.status == "completed" and r.end_date >= today
    ]

    return jsonify({
        "pending_requests": [r.to_dict() for r in all_pending],
        "today_requests": [r.to_dict() for r in today_requests],
        "approved": [r.to_dict() for r in approved[:20]],
        "rejected": [r.to_dict() for r in rejected[:20]],
        "team_calendar": [r.to_dict() for r in upcoming_team],
        "subordinates": [s.to_dict() for s in current_user.subordinates],
    })


@app.route("/api/supervisor/leave/<int:rid>/action", methods=["POST"])
@login_required
def api_supervisor_action(rid):
    data = request.get_json() or {}
    action = data.get("action")
    comment = data.get("comment", "")

    if action not in ("approve", "reject", "more_info"):
        return jsonify({"error": "Invalid action."}), 400

    leave_req = LeaveRequest.query.get_or_404(rid)
    process_approval(leave_req, current_user, action, comment)
    db.session.commit()
    return jsonify({"message": f"Leave {action}d.", "request": leave_req.to_dict()})


@app.route("/api/supervisor/conflict-check", methods=["POST"])
@login_required
def api_conflict_check():
    data = request.get_json() or {}
    result = check_unit_conflict(
        data.get("unit_id"),
        date.fromisoformat(data["start_date"]),
        date.fromisoformat(data["end_date"]),
        data.get("exclude_request_id"),
    )
    return jsonify(result)


# ── HR API ───────────────────────────────────────────────────

@app.route("/api/hr/dashboard")
@login_required
@role_required("HR Officer")
def api_hr_dashboard():
    pending = get_pending_for_approver(current_user, "hr")
    all_requests = LeaveRequest.query.filter(
        LeaveRequest.status.in_([
            "supervisor_approved", "medical_director_approved",
            "hr_pending", "hr_approved", "completed", "hr_rejected",
        ])
    ).order_by(LeaveRequest.created_at.desc()).limit(50).all()

    staff_count = User.query.filter_by(is_active=True).count()
    return jsonify({
        "pending_requests": [r.to_dict() for r in pending],
        "recent_requests": [r.to_dict() for r in all_requests],
        "total_staff": staff_count,
    })


@app.route("/api/hr/leave/<int:rid>/action", methods=["POST"])
@login_required
@role_required("HR Officer")
def api_hr_action(rid):
    data = request.get_json() or {}
    action = data.get("action")
    comment = data.get("comment", "")

    if action not in ("approve", "reject", "return_to_supervisor"):
        return jsonify({"error": "Invalid action."}), 400

    leave_req = LeaveRequest.query.get_or_404(rid)
    process_approval(leave_req, current_user, action, comment)
    db.session.commit()
    return jsonify({"message": f"Leave {action.replace('_', ' ')}.", "request": leave_req.to_dict()})


@app.route("/api/hr/staff")
@login_required
@role_required("HR Officer")
def api_hr_staff():
    users = User.query.filter_by(is_active=True).all()
    return jsonify({"staff": [u.to_dict() for u in users]})


@app.route("/api/hr/reports")
@login_required
@role_required("HR Officer")
def api_hr_reports():
    from sqlalchemy import func

    by_dept = db.session.query(
        Department.name,
        func.count(LeaveRequest.id),
    ).join(User, User.department_id == Department.id).join(
        LeaveRequest, LeaveRequest.employee_id == User.id
    ).filter(LeaveRequest.status == "completed").group_by(Department.name).all()

    by_type = db.session.query(
        LeaveType.name,
        func.count(LeaveRequest.id),
    ).join(LeaveRequest).filter(
        LeaveRequest.status == "completed"
    ).group_by(LeaveType.name).all()

    pending_count = LeaveRequest.query.filter(
        LeaveRequest.status.in_(["supervisor_pending", "hr_pending", "medical_director_pending"])
    ).count()

    return jsonify({
        "by_department": [{"department": d, "count": c} for d, c in by_dept],
        "by_type": [{"type": t, "count": c} for t, c in by_type],
        "pending_approvals": pending_count,
        "total_completed": LeaveRequest.query.filter_by(status="completed").count(),
    })


# ── IT Admin API ─────────────────────────────────────────────

@app.route("/api/it/dashboard")
@login_required
@role_required("IT Administrator")
def api_it_dashboard():
    total = User.query.count()
    locked = User.query.filter_by(is_locked=True).count()
    nurses = User.query.join(Position).filter(Position.staff_category == "Nurses").count()
    doctors = User.query.join(Position).filter(Position.staff_category == "Doctors").count()
    departments = Department.query.count()
    recent_logins = LoginHistory.query.order_by(LoginHistory.created_at.desc()).limit(20).all()
    recent_audits = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(20).all()

    return jsonify({
        "total_users": total,
        "total_nurses": nurses,
        "total_doctors": doctors,
        "locked_accounts": locked,
        "departments": departments,
        "recent_logins": [l.to_dict() for l in recent_logins],
        "recent_audits": [a.to_dict() for a in recent_audits],
    })


@app.route("/api/it/users")
@login_required
@role_required("IT Administrator")
def api_it_users():
    users = User.query.order_by(User.created_at.desc()).all()
    return jsonify({"users": [u.to_dict() for u in users]})


@app.route("/api/it/users", methods=["POST"])
@login_required
@role_required("IT Administrator")
def api_it_create_user():
    data = request.get_json() or {}
    required = ["employee_id", "staff_number", "full_name", "email", "department_id",
                "position_id", "role_id", "username"]
    for field in required:
        if not data.get(field):
            return jsonify({"error": f"Missing field: {field}"}), 400

    if User.query.filter(
        (User.username == data["username"]) |
        (User.email == data["email"]) |
        (User.employee_id == data["employee_id"])
    ).first():
        return jsonify({"error": "Username, email, or employee ID already exists."}), 400

    user = User(
        employee_id=data["employee_id"],
        staff_number=data["staff_number"],
        username=data["username"],
        full_name=data["full_name"],
        email=data["email"],
        phone=data.get("phone", ""),
        department_id=data["department_id"],
        unit_id=data.get("unit_id"),
        position_id=data["position_id"],
        employment_type=data.get("employment_type", "Permanent"),
        supervisor_id=data.get("supervisor_id"),
        role_id=data["role_id"],
        must_change_password=True,
    )
    password = data.get("password", Config.DEFAULT_PASSWORD)
    user.set_password(password)
    db.session.add(user)
    db.session.flush()
    ensure_leave_balances(user)
    log_audit(current_user.id, "user_created", f"Created account for {user.username}")
    db.session.commit()
    return jsonify({"message": "User created.", "user": user.to_dict()})


@app.route("/api/it/users/<int:uid>", methods=["PUT"])
@login_required
@role_required("IT Administrator")
def api_it_update_user(uid):
    user = User.query.get_or_404(uid)
    data = request.get_json() or {}

    for field in ["full_name", "email", "phone", "department_id", "unit_id",
                  "position_id", "employment_type", "supervisor_id", "role_id"]:
        if field in data:
            setattr(user, field, data[field])

    log_audit(current_user.id, "user_updated", f"Updated account {user.username}")
    db.session.commit()
    return jsonify({"message": "User updated.", "user": user.to_dict()})


@app.route("/api/it/users/<int:uid>", methods=["DELETE"])
@login_required
@role_required("IT Administrator")
def api_it_delete_user(uid):
    user = User.query.get_or_404(uid)
    if user.id == current_user.id:
        return jsonify({"error": "Cannot delete your own account."}), 400
    user.is_active = False
    log_audit(current_user.id, "user_deleted", f"Deactivated account {user.username}")
    db.session.commit()
    return jsonify({"message": "User deactivated."})


@app.route("/api/it/users/<int:uid>/reset-password", methods=["POST"])
@login_required
@role_required("IT Administrator")
def api_it_reset_password(uid):
    user = User.query.get_or_404(uid)
    user.set_password(Config.DEFAULT_PASSWORD)
    user.must_change_password = True
    log_audit(current_user.id, "password_reset", f"Reset password for {user.username}")
    db.session.commit()
    return jsonify({"message": f"Password reset to default ({Config.DEFAULT_PASSWORD})."})


@app.route("/api/it/users/<int:uid>/lock", methods=["POST"])
@login_required
@role_required("IT Administrator")
def api_it_lock_user(uid):
    user = User.query.get_or_404(uid)
    data = request.get_json() or {}
    user.is_locked = data.get("lock", True)
    action = "locked" if user.is_locked else "unlocked"
    log_audit(current_user.id, f"account_{action}", f"Account {user.username} {action}")
    db.session.commit()
    return jsonify({"message": f"Account {action}."})


@app.route("/api/it/departments")
@login_required
@role_required("IT Administrator")
def api_it_departments():
    depts = Department.query.all()
    return jsonify({"departments": [
        {"id": d.id, "name": d.name, "code": d.code, "workflow_type": d.workflow_type}
        for d in depts
    ]})


@app.route("/api/it/units")
@login_required
@role_required("IT Administrator")
def api_it_units():
    dept_id = request.args.get("department_id", type=int)
    query = Unit.query
    if dept_id:
        query = query.filter_by(department_id=dept_id)
    units = query.all()
    return jsonify({"units": [
        {"id": u.id, "name": u.name, "department_id": u.department_id}
        for u in units
    ]})


@app.route("/api/it/positions")
@login_required
@role_required("IT Administrator")
def api_it_positions():
    positions = Position.query.all()
    return jsonify({"positions": [
        {"id": p.id, "title": p.title, "staff_category": p.staff_category}
        for p in positions
    ]})


@app.route("/api/it/roles")
@login_required
@role_required("IT Administrator")
def api_it_roles():
    roles = Role.query.all()
    return jsonify({"roles": [{"id": r.id, "name": r.name} for r in roles]})


@app.route("/api/it/supervisors")
@login_required
@role_required("IT Administrator")
def api_it_supervisors():
    supervisors = User.query.join(Role).filter(
        Role.name.in_(["Supervisor", "HR Officer"])
    ).all()
    return jsonify({"supervisors": [
        {"id": s.id, "full_name": s.full_name, "username": s.username}
        for s in supervisors
    ]})


@app.route("/api/it/reports")
@login_required
@role_required("IT Administrator")
def api_it_reports():
    from sqlalchemy import func

    by_role = db.session.query(Role.name, func.count(User.id)).join(User).group_by(Role.name).all()
    by_dept = db.session.query(Department.name, func.count(User.id)).join(
        User, User.department_id == Department.id
    ).group_by(Department.name).all()

    return jsonify({
        "by_role": [{"role": r, "count": c} for r, c in by_role],
        "by_department": [{"department": d, "count": c} for d, c in by_dept],
        "total_active": User.query.filter_by(is_active=True).count(),
        "total_locked": User.query.filter_by(is_locked=True).count(),
    })


# ── File Upload ──────────────────────────────────────────────

ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg", "doc", "docx"}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route("/api/employee/leave/<int:rid>/upload", methods=["POST"])
@login_required
def api_upload_attachment(rid):
    leave_req = LeaveRequest.query.filter_by(id=rid, employee_id=current_user.id).first_or_404()
    if "file" not in request.files:
        return jsonify({"error": "No file provided."}), 400

    file = request.files["file"]
    if not file.filename or not allowed_file(file.filename):
        return jsonify({"error": "Invalid file type."}), 400

    ext = file.filename.rsplit(".", 1)[1].lower()
    filename = f"{uuid.uuid4().hex}.{ext}"
    file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))

    attachment = Attachment(
        leave_request_id=leave_req.id,
        filename=filename,
        original_name=secure_filename(file.filename),
        file_type=ext,
    )
    db.session.add(attachment)
    db.session.commit()
    return jsonify({"message": "File uploaded.", "attachment": attachment.to_dict()})


# ── Calendar API ─────────────────────────────────────────────

@app.route("/api/calendar")
@login_required
def api_calendar():
    dept_id = request.args.get("department_id", type=int)
    query = LeaveRequest.query.filter(
        LeaveRequest.status == "completed",
        LeaveRequest.end_date >= date.today(),
    )
    if dept_id:
        query = query.join(User).filter(User.department_id == dept_id)
    requests = query.all()
    return jsonify({"events": [r.to_dict() for r in requests]})


if __name__ == "__main__":
    seed_database(app)
    app.run(debug=True, port=5000)
