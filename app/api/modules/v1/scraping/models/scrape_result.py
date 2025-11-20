from typing import Optional
from sqlmodel import Field, SQLModel


class ScrapeResult(SQLModel, table=True):
    __tablename__ = "scrape_results"

    id: Optional[int] = Field(default=None, primary_key=True, index=True)
    url: str = Field(max_length=500)
    title: Optional[str] = Field(default=None, max_length=500)
    content: Optional[str] = Field(default=None)
