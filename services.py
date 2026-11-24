"""Business rules: status changes and audit logging. All writes happen here."""
from fastapi import HTTPException

import agent
from models import AuditLog, ChangeRequest, User

# The ONLY allowed status moves.
ALLOWED = {
    "pending": ["agent_reviewed"],
    "agent_reviewed": ["approved", "rejected"],
}


def log(session, actor, action, change_id, details=None):
    session.add(AuditLog(actor=actor, action=action,
                         change_request_id=change_id, details=details))


def move_status(cr: ChangeRequest, new_status: str):
    if new_status not in ALLOWED.get(cr.status, []):
        raise HTTPException(409, f"Cannot go from '{cr.status}' to '{new_status}'")
    cr.status = new_status


def run_agent_review(session, cr: ChangeRequest):
    if cr.status != "pending":
        raise HTTPException(409, f"Already '{cr.status}', cannot review again")

    try:
        summary = agent.review(cr.title, cr.description)
    except Exception as e:
        log(session, "agent", "review_failed", cr.id, {"error": str(e)})
        session.commit()  # status stays 'pending'
        raise HTTPException(502, "AI review failed, see audit log")

    cr.risk_summary = summary.model_dump()  # the agent's only write
    move_status(cr, "agent_reviewed")       # the service moves the status
    log(session, "agent", "review_done", cr.id, cr.risk_summary)
    session.commit()
    session.refresh(cr)
    return cr


def decide(session, cr: ChangeRequest, user: User, decision: str):
    move_status(cr, decision)  # "approved" or "rejected"
    log(session, user.username, decision, cr.id)
    session.commit()
    session.refresh(cr)
    return cr
