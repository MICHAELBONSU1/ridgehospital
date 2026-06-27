from datetime import datetime, timezone

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

db = SQLAlchemy()


def utcnow():
    return datetime.now(timezone.utc)


class Role(db.Model):
    __tablename__ = "roles"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    description = db.Column(db.String(255))
    users = db.relationship("User", back_populates="role")


class Department(db.Model):
    __tablename__ = "departments"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    code = db.Column(db.String(20), unique=True, nullable=False)
    workflow_type = db.Column(db.String(30), default="standard")
    units = db.relationship("Unit", back_populates="department", lazy="dynamic")
    users = db.relationship("User", back_populates="department", foreign_keys="User.department_id")


class Unit(db.Model):
    __tablename__ = "units"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey("departments.id"), nullable=False)
    department = db.relationship("Department", back_populates="units")
    users = db.relationship("User", back_populates="unit", foreign_keys="User.unit_id")


class Position(db.Model):
    __tablename__ = "positions"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    staff_category = db.Column(db.String(50), nullable=False)
    users = db.relationship("User", back_populates="position")


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.String(20), unique=True, nullable=False)
    staff_number = db.Column(db.String(20), unique=True, nullable=False)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(20))
    department_id = db.Column(db.Integer, db.ForeignKey("departments.id"))
    unit_id = db.Column(db.Integer, db.ForeignKey("units.id"))
    position_id = db.Column(db.Integer, db.ForeignKey("positions.id"))
    employment_type = db.Column(db.String(30), default="Permanent")
    supervisor_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    role_id = db.Column(db.Integer, db.ForeignKey("roles.id"), nullable=False)
    must_change_password = db.Column(db.Boolean, default=True)
    is_locked = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=utcnow)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)

    role = db.relationship("Role", back_populates="users")
    department = db.relationship("Department", back_populates="users", foreign_keys=[department_id])
    unit = db.relationship("Unit", back_populates="users", foreign_keys=[unit_id])
    position = db.relationship("Position", back_populates="users")
    supervisor = db.relationship("User", remote_side=[id], backref="subordinates")
    leave_requests = db.relationship("LeaveRequest", back_populates="employee", foreign_keys="LeaveRequest.employee_id")
    leave_balances = db.relationship("LeaveBalance", back_populates="user")
    notifications = db.relationship("Notification", back_populates="user", foreign_keys="Notification.user_id")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self, include_sensitive=False):
        data = {
            "id": self.id,
            "employee_id": self.employee_id,
            "staff_number": self.staff_number,
            "username": self.username,
            "full_name": self.full_name,
            "email": self.email,
            "phone": self.phone,
            "department": self.department.name if self.department else None,
            "department_id": self.department_id,
            "unit": self.unit.name if self.unit else None,
            "unit_id": self.unit_id,
            "position": self.position.title if self.position else None,
            "position_id": self.position_id,
            "staff_category": self.position.staff_category if self.position else None,
            "employment_type": self.employment_type,
            "supervisor_id": self.supervisor_id,
            "supervisor_name": self.supervisor.full_name if self.supervisor else None,
            "role": self.role.name if self.role else None,
            "role_id": self.role_id,
            "must_change_password": self.must_change_password,
            "is_locked": self.is_locked,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        return data


class LeaveType(db.Model):
    __tablename__ = "leave_types"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    code = db.Column(db.String(10), unique=True, nullable=False)
    default_days = db.Column(db.Integer, default=0)
    requires_document = db.Column(db.Boolean, default=False)
    is_paid = db.Column(db.Boolean, default=True)
    requests = db.relationship("LeaveRequest", back_populates="leave_type")


class LeaveBalance(db.Model):
    __tablename__ = "leave_balances"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    leave_type_id = db.Column(db.Integer, db.ForeignKey("leave_types.id"), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    total_days = db.Column(db.Float, default=0)
    used_days = db.Column(db.Float, default=0)
    pending_days = db.Column(db.Float, default=0)

    user = db.relationship("User", back_populates="leave_balances")
    leave_type = db.relationship("LeaveType")

    @property
    def remaining_days(self):
        return self.total_days - self.used_days - self.pending_days


class LeaveRequest(db.Model):
    __tablename__ = "leave_requests"

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    leave_type_id = db.Column(db.Integer, db.ForeignKey("leave_types.id"), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    days_requested = db.Column(db.Float, nullable=False)
    reason = db.Column(db.Text)
    status = db.Column(db.String(30), default="draft")
    current_stage = db.Column(db.String(30), default="draft")
    created_at = db.Column(db.DateTime, default=utcnow)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)
    submitted_at = db.Column(db.DateTime)

    employee = db.relationship("User", back_populates="leave_requests", foreign_keys=[employee_id])
    leave_type = db.relationship("LeaveType", back_populates="requests")
    approvals = db.relationship("LeaveApproval", back_populates="leave_request", order_by="LeaveApproval.created_at")
    attachments = db.relationship("Attachment", back_populates="leave_request")

    def to_dict(self):
        return {
            "id": self.id,
            "employee_id": self.employee_id,
            "employee_name": self.employee.full_name if self.employee else None,
            "employee_department": self.employee.department.name if self.employee and self.employee.department else None,
            "employee_unit": self.employee.unit.name if self.employee and self.employee.unit else None,
            "leave_type": self.leave_type.name if self.leave_type else None,
            "leave_type_id": self.leave_type_id,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "days_requested": self.days_requested,
            "reason": self.reason,
            "status": self.status,
            "current_stage": self.current_stage,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "submitted_at": self.submitted_at.isoformat() if self.submitted_at else None,
            "approvals": [a.to_dict() for a in self.approvals],
            "attachments": [a.to_dict() for a in self.attachments],
        }


class LeaveApproval(db.Model):
    __tablename__ = "leave_approvals"

    id = db.Column(db.Integer, primary_key=True)
    leave_request_id = db.Column(db.Integer, db.ForeignKey("leave_requests.id"), nullable=False)
    approver_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    stage = db.Column(db.String(30), nullable=False)
    action = db.Column(db.String(30), nullable=False)
    comment = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=utcnow)

    leave_request = db.relationship("LeaveRequest", back_populates="approvals")
    approver = db.relationship("User", foreign_keys=[approver_id])

    def to_dict(self):
        return {
            "id": self.id,
            "approver_id": self.approver_id,
            "approver_name": self.approver.full_name if self.approver else None,
            "stage": self.stage,
            "action": self.action,
            "comment": self.comment,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Notification(db.Model):
    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    title = db.Column(db.String(150), nullable=False)
    message = db.Column(db.Text, nullable=False)
    link = db.Column(db.String(255))
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=utcnow)

    user = db.relationship("User", back_populates="notifications", foreign_keys=[user_id])

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "message": self.message,
            "link": self.link,
            "is_read": self.is_read,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class PasswordHistory(db.Model):
    __tablename__ = "password_history"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow)


class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    action = db.Column(db.String(100), nullable=False)
    details = db.Column(db.Text)
    ip_address = db.Column(db.String(45))
    created_at = db.Column(db.DateTime, default=utcnow)

    user = db.relationship("User", foreign_keys=[user_id])

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "user_name": self.user.full_name if self.user else "System",
            "action": self.action,
            "details": self.details,
            "ip_address": self.ip_address,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class LoginHistory(db.Model):
    __tablename__ = "login_history"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    username = db.Column(db.String(50))
    success = db.Column(db.Boolean, default=False)
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=utcnow)

    user = db.relationship("User", foreign_keys=[user_id])

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "username": self.username,
            "success": self.success,
            "ip_address": self.ip_address,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Attachment(db.Model):
    __tablename__ = "attachments"

    id = db.Column(db.Integer, primary_key=True)
    leave_request_id = db.Column(db.Integer, db.ForeignKey("leave_requests.id"), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    original_name = db.Column(db.String(255), nullable=False)
    file_type = db.Column(db.String(50))
    uploaded_at = db.Column(db.DateTime, default=utcnow)

    leave_request = db.relationship("LeaveRequest", back_populates="attachments")

    def to_dict(self):
        return {
            "id": self.id,
            "filename": self.filename,
            "original_name": self.original_name,
            "file_type": self.file_type,
            "uploaded_at": self.uploaded_at.isoformat() if self.uploaded_at else None,
        }


class Holiday(db.Model):
    __tablename__ = "holidays"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    date = db.Column(db.Date, nullable=False, unique=True)
    is_recurring = db.Column(db.Boolean, default=False)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "date": self.date.isoformat(),
            "is_recurring": self.is_recurring,
        }
