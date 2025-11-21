from typing import Optional
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel


class WebScraper(SQLModel, table=True):
    __tablename__ = "scrape_results"

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    url: str = Field(max_length=500)
    title: Optional[str] = Field(default=None, max_length=500)
    content: Optional[str] = Field(default=None)

    # Use string forward reference instead of importing DataRevision
    # revisions: List["DataRevision"] = Relationship(back_populates="scrape_result")
