from sqlmodel import Session
from app.api.modules.v1.jurisdictions.models.jurisdiction_models import Jurisdiction
from app.api.modules.v1.jurisdictions.schemas.jurisdiction_schemas import JurisdictionCreate


def create_jurisdiction(session: Session, project_id: str, data: JurisdictionCreate):
    jurisdiction = Jurisdiction(
        **data.dict(),
        project_id=project_id
    )
    session.add(jurisdiction)
    session.commit()
    session.refresh(jurisdiction)
    return jurisdiction
