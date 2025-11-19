from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel


class ProjectCreate(SQLModel):
    name: str
    settings: Optional[dict] = {}
    ai_prompt: Optional[str] = None


class ProjectRead(ProjectCreate):
    id: str
    created_at: datetime
