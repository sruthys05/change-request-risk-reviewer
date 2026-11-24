"""Database tables and the Pydantic schema for the LLM's answer."""
from datetime import datetime, timezone
from typing import Literal, Optional

import pydantic
from sqlmodel import JSON, Column, Field, SQLModel


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(unique=True)
    role: str  # "engineer" or "approver"


class ChangeRequest(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    description: str
    status: str = "pending"  # pending -> agent_reviewed -> approved / rejected
    risk_summary: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    created_by: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AuditLog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    actor: str  # a username, or "agent"
    action: str
    change_request_id: int
    details: Optional[dict] = Field(default=None, sa_column=Column(JSON))


class RiskSummary(pydantic.BaseModel):
    """The exact shape the LLM must return."""
    risk: Literal["low", "medium", "high"]
    reasons: list[str] = pydantic.Field(min_length=1)
    recommendation: str


class NewChange(pydantic.BaseModel):
    title: str
    description: str
