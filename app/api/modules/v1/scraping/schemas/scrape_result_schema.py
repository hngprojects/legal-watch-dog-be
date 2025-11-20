from pydantic import BaseModel


class ScrapeResultCreate(BaseModel):
    url: str


class ScrapeResultOut(BaseModel):
    id: int
    url: str
    title: str | None
    content: str | None

    class Config:
        orm_mode = True
