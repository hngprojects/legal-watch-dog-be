from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import uuid4, UUID
from sqlalchemy import Column, String
from sqlalchemy.dialects.postgresql import JSONB


class Organization(SQLModel, table=True):
    __tablename__ = "organization"

    org_id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str = Field(index=True)
    industry: Optional[str] = Field(default=None, sa_column=Column(String))
    billing_info: Optional[Dict[str, Any]] = Field(
        default=None, sa_column=Column(JSONB)
    )
    settings: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSONB))


class Role(SQLModel, table=True):
    __tablename__ = "role"

    role_id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str = Field(index=True)


class User(SQLModel, table=True):
    __tablename__ = "user"

    user_id: UUID = Field(default_factory=uuid4, primary_key=True)
    org_id: UUID = Field(foreign_key="organization.org_id")
    role_id: UUID = Field(foreign_key="role.role_id")
    email: str = Field(unique=True, index=True)
    hashed_password: str = Field(sa_column=Column(String))
    status: str = Field(default="active")



class RefreshToken(SQLModel, table=True):
    __tablename__ = "refresh_tokens"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    token: str = Field(sa_column=Column(String, unique=True, index=True))
    user_id: UUID = Field(foreign_key="user.user_id")
    expires_at: datetime
    revoked: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by_ip: Optional[str] = Field(default=None, sa_column=Column(String))
