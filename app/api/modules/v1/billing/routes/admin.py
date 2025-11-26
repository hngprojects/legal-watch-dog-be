import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.core.logger import setup_logging
from app.api.db.database import get_db
from app.api.modules.v1.auth.dependencies import require_admin
from app.api.modules.v1.billing.schemas.responses import BillingMetricsResponse
from app.api.modules.v1.billing.services.billing_service import BillingService
from app.api.modules.v1.users.models import User

setup_logging()
logger = logging.getLogger(__name__)


router = APIRouter(prefix="/admin/billing", tags=["Admin - Billing"])


def get_billing_service(db: AsyncSession = Depends(get_db)) -> BillingService:
    """Dependency to get BillingService instance"""
    return BillingService(db)


@router.get(
    "/metrics",
    response_model=BillingMetricsResponse,
    summary="Get billing metrics",
    description="Retrieves billing analytics and metrics. Admin only."
)
async def get_billing_metrics(
    current_user: User = Depends(require_admin),
    billing_service: BillingService = Depends(get_billing_service)
) -> BillingMetricsResponse:
    """
    Get billing metrics for admin dashboard.
    
    Requires admin role.
    
    Returns:
    - Total accounts
    - Active subscriptions
    - Trial accounts
    - Past due / blocked accounts
    - MRR / ARR
    - ARPU
    """
    logger.info("GET /admin/billing/metrics - Fetch billing metrics", extra={
        "user_id": str(current_user.id),
        "user_role": current_user.role
    })
    
    try:
        metrics = await billing_service.get_billing_metrics()
        
        logger.info(
            "Billing metrics retrieved successfully",
            extra={
                "total_accounts": metrics.total_accounts,
                "active_subscriptions": metrics.active_subscriptions
            }
        )
        
        return metrics
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to fetch billing metrics",
            exc_info=True,
            extra={"error": str(e)}
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve billing metrics"
        )