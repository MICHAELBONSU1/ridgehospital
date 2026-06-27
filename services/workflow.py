"""Approval workflow configuration per department type."""

WORKFLOW_CHAINS = {
    "standard": ["supervisor", "hr"],
    "medical": ["supervisor", "medical_director", "hr"],
    "nursing": ["supervisor", "hr"],
    "laboratory": ["supervisor", "hr"],
    "pharmacy": ["supervisor", "hr"],
    "billing": ["supervisor", "hr"],
    "corporate": ["supervisor", "hr"],
    "security": ["supervisor", "hr"],
}

STAGE_STATUS_MAP = {
    "supervisor": {
        "pending": "supervisor_pending",
        "approved": "supervisor_approved",
        "rejected": "supervisor_rejected",
    },
    "medical_director": {
        "pending": "medical_director_pending",
        "approved": "medical_director_approved",
        "rejected": "medical_director_rejected",
    },
    "hr": {
        "pending": "hr_pending",
        "approved": "hr_approved",
        "rejected": "hr_rejected",
    },
}


def get_workflow_chain(department):
    if not department:
        return WORKFLOW_CHAINS["standard"]
    return WORKFLOW_CHAINS.get(department.workflow_type, WORKFLOW_CHAINS["standard"])


def get_next_stage(chain, current_stage):
    if current_stage == "submitted":
        return chain[0] if chain else None
    try:
        idx = chain.index(current_stage)
        if idx + 1 < len(chain):
            return chain[idx + 1]
    except ValueError:
        pass
    return None


def get_stage_status(stage, action):
    mapping = STAGE_STATUS_MAP.get(stage, {})
    return mapping.get(action, action)


def get_approver_for_stage(user, stage):
    """Walk supervisor chain to find approver for a given stage."""
    if stage == "supervisor":
        return user.supervisor
    if stage == "medical_director":
        if user.supervisor and user.supervisor.supervisor:
            return user.supervisor.supervisor
        return user.supervisor
    if stage == "hr":
        from models import Role, User

        hr_role = Role.query.filter_by(name="HR Officer").first()
        if hr_role:
            return User.query.filter_by(role_id=hr_role.id, is_active=True).first()
    return None


def stage_label(stage):
    labels = {
        "supervisor": "Supervisor",
        "medical_director": "Medical Director",
        "hr": "HR",
    }
    return labels.get(stage, stage.replace("_", " ").title())
