import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.core.logger import setup_logging
from app.api.db.database import get_db
from app.api.modules.v1.auth.dependencies import get_current_user
from app.api.modules.v1.billing.services.billing_service import BillingService
from app.api.modules.v1.users.models import User

setup_logging()
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/billing/invoices", tags=["Billing - Invoices"])


def get_billing_service(db: AsyncSession = Depends(get_db)) -> BillingService:
    """Dependency to get BillingService instance"""
    return BillingService(db)


@router.get(
    "/{invoice_id}", response_class=RedirectResponse, summary="Download invoice PDF"
)
async def download_invoice_pdf(
    invoice_id: UUID,
    current_user: User = Depends(get_current_user),
    billing_service: BillingService = Depends(get_billing_service),
) -> RedirectResponse:
    """Download invoice PDF"""
    logger.info(
        "GET /billing/invoices/{invoice_id} - Download invoice PDF",
        extra={"invoice_id": str(invoice_id), "user_id": str(current_user.id)},
    )

    try:
        pdf_url = await billing_service.get_invoice_pdf_url(invoice_id=invoice_id)

        logger.info(
            "Invoice PDF URL retrieved",
            extra={"invoice_id": str(invoice_id), "pdf_url": pdf_url},
        )

        return RedirectResponse(url=pdf_url, status_code=status.HTTP_302_FOUND)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to download invoice PDF",
            exc_info=True,
            extra={"invoice_id": str(invoice_id), "error": str(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve invoice PDF",
        )
