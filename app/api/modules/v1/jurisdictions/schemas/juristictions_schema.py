from sqlmodel import SQLModel
from typing import Optional
from datetime import datetime


class JurisdictionCreate(SQLModel):
    name: str
    ai_prompt: Optional[str] = None
    parent_id: Optional[str] = None


class JurisdictionRead(JurisdictionCreate):
    id: str
    project_id: str
    created_at: datetime
