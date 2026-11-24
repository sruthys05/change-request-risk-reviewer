"""API routes. Run with:  uvicorn main:app --reload"""
import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException
from sqlmodel import Session, SQLModel, create_engine, select

import services
from models import AuditLog, ChangeRequest, NewChange, User

engine = create_engine(os.getenv("DB_URL", "sqlite:///changes.db"))


@asynccontextmanager
async def lifespan(app):
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:  # two demo users
        if not s.exec(select(User)).first():
            s.add(User(username="alice", role="engineer"))
            s.add(User(username="bob", role="approver"))
            s.commit()
    yield


app = FastAPI(title="Change Request Risk Reviewer", lifespan=lifespan)


def get_session():
    with Session(engine) as session:
        yield session


def current_user(x_user: str = Header(), session: Session = Depends(get_session)):
    """Simple login: send header  X-User: alice"""
    user = session.exec(select(User).where(User.username == x_user)).first()
    if not user:
        raise HTTPException(401, "Unknown user")
    return user


def approver_only(user: User = Depends(current_user)):
    if user.role != "approver":
        raise HTTPException(403, "Only approvers can do this")
    return user


def get_change(change_id: int, session: Session):
    cr = session.get(ChangeRequest, change_id)
    if not cr:
        raise HTTPException(404, "Change request not found")
    return cr


@app.post("/changes")
def create_change(body: NewChange, user: User = Depends(current_user),
                  session: Session = Depends(get_session)):
    cr = ChangeRequest(title=body.title, description=body.description,
                       created_by=user.username)
    session.add(cr)
    session.commit()
    services.log(session, user.username, "created", cr.id)
    session.commit()
    session.refresh(cr)
    return cr


@app.get("/changes")
def list_changes(user: User = Depends(current_user),
                 session: Session = Depends(get_session)):
    return session.exec(select(ChangeRequest)).all()


@app.get("/changes/{change_id}")
def read_change(change_id: int, user: User = Depends(current_user),
                session: Session = Depends(get_session)):
    return get_change(change_id, session)


@app.post("/changes/{change_id}/review")
def review_change(change_id: int, user: User = Depends(current_user),
                  session: Session = Depends(get_session)):
    return services.run_agent_review(session, get_change(change_id, session))


@app.post("/changes/{change_id}/approve")
def approve(change_id: int, user: User = Depends(approver_only),
            session: Session = Depends(get_session)):
    return services.decide(session, get_change(change_id, session), user, "approved")


@app.post("/changes/{change_id}/reject")
def reject(change_id: int, user: User = Depends(approver_only),
           session: Session = Depends(get_session)):
    return services.decide(session, get_change(change_id, session), user, "rejected")


@app.get("/audit")
def audit(user: User = Depends(current_user), session: Session = Depends(get_session)):
    return session.exec(select(AuditLog).order_by(AuditLog.id)).all()
