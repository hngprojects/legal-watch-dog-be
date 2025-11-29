from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.core.dependencies.auth import TenantGuard, get_current_user
from app.api.db.database import get_db
from app.api.modules.v1.jurisdictions.service.jurisdiction_service import OrgResourceGuard
from app.api.modules.v1.scraping.routes.docs.source_discovery_docs import (
    accept_sources_responses,
    suggest_sources_responses,
)
from app.api.modules.v1.scraping.schemas.source_discovery_schema import SuggestionRequest
from app.api.modules.v1.scraping.schemas.source_service import SourceAccept, SourceCreate
from app.api.modules.v1.scraping.service.source_discovery_service import SourceDiscoveryService
from app.api.modules.v1.scraping.service.source_service import SourceService
from app.api.modules.v1.users.models.users_model import User
from app.api.utils.response_payloads import error_response, success_response

router = APIRouter(
    tags=["AI Source Discovery"],
    dependencies=[Depends(TenantGuard), Depends(OrgResourceGuard)],
)


@router.post(
    "/sources/suggest",
    summary="Suggest official sources using AI",
    responses=suggest_sources_responses,
)
async def suggest_sources(payload: SuggestionRequest):
    """Triggers the AI Researcher Agent to find valid sources.

    This endpoint combines the jurisdiction name and description to provide
    broad context to the AI Agent, allowing it to find more accurate official sources
    for legal monitoring and compliance purposes.

    Args:
        payload (SuggestionRequest): The request payload containing:
            - jurisdiction_name (str): Name of the jurisdiction to find sources for
            - jurisdiction_description (str): Description of jurisdiction's legal scope
            - project_description (str): Project goal for finding relevant sources

    Returns:
        JSONResponse: Success response with list of AI-suggested sources.

    Raises:
        HTTPException: 500 if configuration error or discovery agent fails.

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


@router.post(
    "/sources/accept-suggestions",
    summary="Accept AI-suggested sources",
    responses=accept_sources_responses,
)
async def accept_suggested_sources(
    payload: SourceAccept,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Accept AI-suggested sources and convert them to active sources.

    This endpoint takes the output from the AI suggestion endpoint and creates
    actual source records in the database. It combines the suggested source data
    with required creation parameters and validates for duplicates before creation.

    Args:
        payload (SourceAccept): The acceptance payload containing:
            - suggested_sources (List[Dict]): List of suggested sources from AI with:
              - title (str): Source name
              - url (HttpUrl): Source URL
              - snippet (str): Source description
              - confidence_reason (str): Why AI recommends this source
              - is_official (bool): Whether this is an official source
            - jurisdiction_id (uuid.UUID): Parent jurisdiction UUID
            - source_type (SourceType): Type of source (web, pdf, api)
            - scrape_frequency (str): Scraping frequency (e.g., DAILY, HOURLY)
            - scraping_rules (Optional[Dict]): Custom extraction rules
        db (AsyncSession): Database session.
        current_user (User): Authenticated user.

    Returns:
        JSONResponse: Success response with created sources and count, or error response.

    Raises:
        HTTPException: 400 if duplicate URLs exist or invalid data, 422 if validation fails.

    """
    try:
        sources_to_create = []
        for suggested in payload.suggested_sources:
            source_create = SourceCreate(
                jurisdiction_id=payload.jurisdiction_id,
                name=suggested.get("title", ""),
                url=suggested.get("url", ""),
                source_type=payload.source_type,
                scrape_frequency=payload.scrape_frequency,
                scraping_rules=payload.scraping_rules,
                auth_details=None,
            )
            sources_to_create.append(source_create)

        service = SourceService()
        sources = await service.bulk_create_sources(db, sources_to_create)

        return success_response(
            status_code=status.HTTP_201_CREATED,
            message="Suggested sources accepted and created successfully",
            data={
                "sources": [source.model_dump() for source in sources],
                "count": len(sources),
            },
        )

    except HTTPException:
        raise
    except ValueError as ve:
        return error_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message="Invalid suggestion data",
            error="INVALID_SUGGESTION_DATA",
            errors={"details": str(ve)},
        )
    except Exception as e:
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to accept suggested sources",
            error="ACCEPT_SUGGESTIONS_FAILED",
            errors={"details": str(e)},
        )
