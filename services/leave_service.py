from datetime import date, datetime, timedelta, timezone

from flask import request

from models import (
    AuditLog,
    LeaveApproval,
    LeaveBalance,
    LeaveRequest,
    LoginHistory,
    PasswordHistory,
    db,
)
from services.notifications import (
    check_unit_conflict,
    create_notification,
    notify_leave_final,
    notify_leave_submitted,
    notify_stage_approved,
)
from services.workflow import (
    get_approver_for_stage,
    get_next_stage,
    get_stage_status,
    get_workflow_chain,
    stage_label,
)


def log_audit(user_id, action, details=None):
    entry = AuditLog(
        user_id=user_id,
        action=action,
        details=details,
        ip_address=request.remote_addr if request else None,
    )
    db.session.add(entry)


def log_login(user_id, username, success):
    entry = LoginHistory(
        user_id=user_id,
        username=username,
        success=success,
        ip_address=request.remote_addr if request else None,
        user_agent=request.user_agent.string[:255] if request and request.user_agent else None,
    )
    db.session.add(entry)


def change_password(user, new_password, old_password=None):
    if old_password and not user.check_password(old_password):
        return False, "Current password is incorrect."

    history = PasswordHistory.query.filter_by(user_id=user.id).order_by(
        PasswordHistory.created_at.desc()
    ).limit(5).all()
    for h in history:
        from werkzeug.security import check_password_hash

        if check_password_hash(h.password_hash, new_password):
            return False, "You cannot reuse a recent password."

    db.session.add(PasswordHistory(user_id=user.id, password_hash=user.password_hash))
    user.set_password(new_password)
    user.must_change_password = False
    log_audit(user.id, "password_changed", "User changed password")
    return True, "Password updated successfully."


def calculate_days(start_date, end_date):
    if isinstance(start_date, str):
        start_date = date.fromisoformat(start_date)
    if isinstance(end_date, str):
        end_date = date.fromisoformat(end_date)
    return (end_date - start_date).days + 1


def submit_leave_request(leave_request):
    employee = leave_request.employee
    chain = get_workflow_chain(employee.department)
    first_stage = chain[0] if chain else "supervisor"

    leave_request.status = get_stage_status(first_stage, "pending")
    leave_request.current_stage = first_stage
    leave_request.submitted_at = datetime.now(timezone.utc)

    balance = LeaveBalance.query.filter_by(
        user_id=employee.id,
        leave_type_id=leave_request.leave_type_id,
        year=leave_request.start_date.year,
    ).first()
    if balance:
        balance.pending_days += leave_request.days_requested

    notify_leave_submitted(leave_request)
    log_audit(employee.id, "leave_submitted", f"Leave request #{leave_request.id} submitted")
    return leave_request


def process_approval(leave_request, approver, action, comment=None):
    stage = leave_request.current_stage
    employee = leave_request.employee
    chain = get_workflow_chain(employee.department)

    approval = LeaveApproval(
        leave_request_id=leave_request.id,
        approver_id=approver.id,
        stage=stage,
        action=action,
        comment=comment,
    )
    db.session.add(approval)

    if action == "more_info":
        leave_request.status = "more_info_requested"
        create_notification(
            employee.id,
            "More Information Required",
            f"Your supervisor needs more information about your leave request.\n{comment or ''}",
            link="/employee/dashboard",
        )
        log_audit(approver.id, "leave_more_info", f"Request #{leave_request.id}")
        return leave_request

    if action == "return_to_supervisor" and stage == "hr":
        leave_request.current_stage = "supervisor"
        leave_request.status = get_stage_status("supervisor", "pending")
        supervisor = get_approver_for_stage(employee, "supervisor")
        if supervisor:
            create_notification(
                supervisor.id,
                "Leave Returned",
                f"HR returned {employee.full_name}'s leave request for review.",
                link="/supervisor/dashboard",
            )
        log_audit(approver.id, "leave_returned", f"Request #{leave_request.id} returned to supervisor")
        return leave_request

    if action == "reject":
        leave_request.status = get_stage_status(stage, "rejected")
        _release_pending_days(leave_request)
        notify_leave_final(leave_request, approved=False, reason=comment)
        log_audit(approver.id, "leave_rejected", f"Request #{leave_request.id} rejected at {stage}")
        return leave_request

    if action == "approve":
        leave_request.status = get_stage_status(stage, "approved")
        next_stage = get_next_stage(chain, stage)
        if next_stage:
            leave_request.current_stage = next_stage
            leave_request.status = get_stage_status(next_stage, "pending")
            next_approver = get_approver_for_stage(employee, next_stage)
            notify_stage_approved(leave_request, stage_label(stage), next_approver)
        else:
            leave_request.status = "completed"
            leave_request.current_stage = "completed"
            _finalize_leave(leave_request)
            notify_leave_final(leave_request, approved=True)
        log_audit(approver.id, "leave_approved", f"Request #{leave_request.id} approved at {stage}")

    return leave_request


def _release_pending_days(leave_request):
    balance = LeaveBalance.query.filter_by(
        user_id=leave_request.employee_id,
        leave_type_id=leave_request.leave_type_id,
        year=leave_request.start_date.year,
    ).first()
    if balance:
        balance.pending_days = max(0, balance.pending_days - leave_request.days_requested)


def _finalize_leave(leave_request):
    balance = LeaveBalance.query.filter_by(
        user_id=leave_request.employee_id,
        leave_type_id=leave_request.leave_type_id,
        year=leave_request.start_date.year,
    ).first()
    if balance:
        balance.pending_days = max(0, balance.pending_days - leave_request.days_requested)
        balance.used_days += leave_request.days_requested


def cancel_leave_request(leave_request):
    if leave_request.status in ("draft", "supervisor_pending", "more_info_requested"):
        _release_pending_days(leave_request)
        leave_request.status = "cancelled"
        leave_request.current_stage = "cancelled"
        log_audit(leave_request.employee_id, "leave_cancelled", f"Request #{leave_request.id}")
        return True
    return False


def get_pending_for_approver(user, stage):
    from models import User as UserModel

    pending_status = get_stage_status(stage, "pending")
    requests = LeaveRequest.query.filter_by(status=pending_status, current_stage=stage).all()
    result = []
    for req in requests:
        approver = get_approver_for_stage(req.employee, stage)
        if approver and approver.id == user.id:
            result.append(req)
        elif stage == "hr" and user.role.name == "HR Officer":
            result.append(req)
    return result
