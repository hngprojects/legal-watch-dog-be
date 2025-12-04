import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.db.database import get_db
from app.api.modules.v1.hire_specialists.models.specialist_models import SpecialistHire
from app.api.modules.v1.hire_specialists.schemas.specialist_schemas import (
    SpecialistHireRequest,
    SpecialistHireResponse,
)

# Initialize logger
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

router = APIRouter(prefix="/specialists", tags=["Specialists"])


@router.post(
    "/hire-requests", response_model=SpecialistHireResponse, status_code=status.HTTP_201_CREATED
)
async def hire_specialist(request: SpecialistHireRequest, db: AsyncSession = Depends(get_db)):
    """
    Create a new specialist hire request.

    Accepts company information and specialist requirements,
    stores them in the database, and returns a success confirmation.

    Args:
        request: Specialist hire request data
        db: Database session dependency

    Returns:
        SpecialistHireResponse with success message and hire details

    Raises:
        HTTPException: If database operation fails
    """
    try:
        logger.info("Processing hire request for company: %s", request.company_name)

        new_hire = SpecialistHire(
            company_name=request.company_name,
            company_email=request.company_email,
            industry=request.industry,
            brief_description=request.brief_description,
        )

        db.add(new_hire)
        await db.commit()
        await db.refresh(new_hire)

        logger.info("Specialist hire request successfully created with ID: %s", new_hire.id)

        return SpecialistHireResponse(
            success=True,
            message="Specialist hired successfully. A specialist will be sent to you shortly",
            data={
                "id": new_hire.id,
                "company_name": new_hire.company_name,
                "company_email": new_hire.company_email,
                "industry": new_hire.industry,
                "created_at": new_hire.created_at.isoformat(),
            },
        )

    except Exception as e:
        await db.rollback()
        logger.error("Failed to process hire request: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process hire request: {str(e)}",
        )
