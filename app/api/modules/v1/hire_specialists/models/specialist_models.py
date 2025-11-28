
from datetime import datetime
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel


class SpecialistHire(SQLModel, table=True):
    """
    Database model for storing specialist hire requests.

    Tracks company information and specialist requirements for
    immigration and global mobility services.
    """

    __tablename__ = "specialist_hires"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    company_name: str = Field(nullable=False, max_length=255)
    company_email: str = Field(nullable=False, max_length=255)
    industry: str = Field(nullable=False, max_length=255)
    brief_description: str = Field(nullable=False)

    created_at: datetime = Field(default_factory=datetime.utcnow)

    def __repr__(self):
        return (
            f"<SpecialistHire(company={self.company_name}, industry={self.industry})>"
        )
