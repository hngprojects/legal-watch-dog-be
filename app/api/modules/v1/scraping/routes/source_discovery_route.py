from fastapi import APIRouter, status

from app.api.modules.v1.scraping.schemas.source_discovery_schema import SuggestionRequest
from app.api.modules.v1.scraping.service.source_discovery_service import SourceDiscoveryService
from app.api.utils.response_payloads import error_response, success_response

router = APIRouter(tags=["AI Source Discovery"])


@router.post("/sources/suggest", summary="Suggest official sources using AI Researcher")
async def suggest_sources(payload: SuggestionRequest):
    """Triggers the AI Researcher Agent to find valid sources.

    This endpoint combines the jurisdiction name and description to provide
    broad context to the AI Agent, allowing it to find more accurate official sources.

    Args:
        payload (SuggestionRequest): The request payload containing jurisdiction
            details and project goal.

    Returns:
        JSONResponse: Either a success response with the list of sources or an error response.
    """
    try:
        service = SourceDiscoveryService()
        sources = await service.suggest_sources(
            jurisdiction_name=payload.jurisdiction_name,
            jurisdiction_description=payload.jurisdiction_description,
            project_description=payload.project_description,
        )

        return success_response(
            status_code=status.HTTP_200_OK,
            message="Sources suggested successfully",
            data={"sources": sources},
        )

    except ValueError as ve:
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Configuration Error",
            error="CONFIGURATION_ERROR",
            errors={"details": str(ve)},
        )
    except Exception as e:
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Discovery Agent failed",
            error="DISCOVERY_AGENT_FAILED",
            errors={"details": str(e)},
        )
