from datetime import date

from models import LeaveBalance, LeaveType, Notification, User, db


def create_notification(user_id, title, message, link=None):
    notification = Notification(user_id=user_id, title=title, message=message, link=link)
    db.session.add(notification)
    return notification


def notify_leave_submitted(leave_request):
    employee = leave_request.employee
    from services.workflow import get_workflow_chain, get_approver_for_stage

    chain = get_workflow_chain(employee.department)
    first_stage = chain[0] if chain else "supervisor"
    approver = get_approver_for_stage(employee, first_stage)
    if approver:
        create_notification(
            approver.id,
            "New Leave Request",
            f"{employee.full_name} has requested {leave_request.leave_type.name}.",
            link="/supervisor/dashboard",
        )


def notify_stage_approved(leave_request, stage, next_approver):
    employee = leave_request.employee
    if next_approver:
        create_notification(
            next_approver.id,
            "Leave Pending Approval",
            f"{employee.full_name} has been approved by {stage.replace('_', ' ').title()}.",
            link="/hr/dashboard" if stage != "hr" else "/hr/dashboard",
        )


def notify_leave_final(leave_request, approved=True, reason=None):
    employee = leave_request.employee
    if approved:
        create_notification(
            employee.id,
            "Leave Approved",
            "Congratulations! Your leave has been approved.",
            link="/employee/dashboard",
        )
    else:
        msg = "Your leave has been rejected."
        if reason:
            msg += f"\nReason: {reason}"
        create_notification(
            employee.id,
            "Leave Rejected",
            msg,
            link="/employee/dashboard",
        )


def ensure_leave_balances(user, year=None):
    year = year or date.today().year
    leave_types = LeaveType.query.all()
    for lt in leave_types:
        existing = LeaveBalance.query.filter_by(
            user_id=user.id, leave_type_id=lt.id, year=year
        ).first()
        if not existing:
            db.session.add(
                LeaveBalance(
                    user_id=user.id,
                    leave_type_id=lt.id,
                    year=year,
                    total_days=lt.default_days,
                )
            )


def check_unit_conflict(unit_id, start_date, end_date, exclude_request_id=None):
    """Warn if too many staff from same unit are on leave."""
    from models import LeaveRequest

    if not unit_id:
        return {"conflict": False, "count": 0, "staff_on_leave": []}

    unit_users = User.query.filter_by(unit_id=unit_id, is_active=True).all()
    user_ids = [u.id for u in unit_users]
    total_staff = len(user_ids)
    if total_staff == 0:
        return {"conflict": False, "count": 0, "staff_on_leave": []}

    active_statuses = [
        "supervisor_pending",
        "supervisor_approved",
        "medical_director_pending",
        "medical_director_approved",
        "hr_pending",
        "hr_approved",
        "completed",
    ]
    query = LeaveRequest.query.filter(
        LeaveRequest.employee_id.in_(user_ids),
        LeaveRequest.status.in_(active_statuses),
        LeaveRequest.start_date <= end_date,
        LeaveRequest.end_date >= start_date,
    )
    if exclude_request_id:
        query = query.filter(LeaveRequest.id != exclude_request_id)

    overlapping = query.all()
    count = len(overlapping)
    threshold = max(1, int(total_staff * 0.3))
    return {
        "conflict": count >= threshold,
        "count": count,
        "total_staff": total_staff,
        "threshold": threshold,
        "staff_on_leave": [r.employee.full_name for r in overlapping],
    }
