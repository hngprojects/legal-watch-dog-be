from typing import Optional

from pydantic import BaseModel


class ScrapeResultCreate(BaseModel):
    url: str


class ScrapeResultOut(BaseModel):
    id: int
    url: str
    title: Optional[str]
    content: str | None  # fetched from MinIO

    class Config:
        orm_mode = True
