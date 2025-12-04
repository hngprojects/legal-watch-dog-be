
from uuid import uuid4, UUID
from datetime import datetime,timezone
from typing import Optional
from sqlmodel import SQLModel, Field


class ApiKey(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    key_hash: str

    # The organization this key belongs to
    organization_id: UUID

    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.now(timezone.utc))
    last_used_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    description: Optional[str] = None
