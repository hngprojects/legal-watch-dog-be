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
    """Trigger the AI Researcher Agent to find valid official sources.

    Combines jurisdiction context with project description to guide AI discovery
    of accurate official sources for legal monitoring and compliance purposes.

    Args:
        payload: The suggestion request containing jurisdiction name, description,
            optional jurisdiction_prompt, project_description, and search_query.

    Returns:
        dict: Success response with list of AI-suggested sources in data field.

    Raises:
        HTTPException: 500 for configuration error or discovery agent failure.

    """
    try:
        service = SourceDiscoveryService()
        sources = await service.suggest_sources(
            jurisdiction_name=payload.jurisdiction_name,
            jurisdiction_description=payload.jurisdiction_description,
            jurisdiction_prompt=payload.jurisdiction_prompt,
            project_description=payload.project_description,
            search_query=payload.search_query,
        )

        return success_response(
            status_code=status.HTTP_200_OK,
            message="Sources suggested successfully",
            data={"sources": [source.model_dump() for source in sources]},
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
    """Accept AI-suggested sources and create them as active source records.

    Converts AI-suggested sources into database records. Validates for duplicates
    and combines suggested data with creation parameters before persistence.

    Args:
        payload: Acceptance request with suggested sources, jurisdiction_id,
            source_type, scrape_frequency, and optional scraping_rules.
        db: Database session for persistence operations.
        current_user: Authenticated user performing the acceptance.

    Returns:
        dict: Success response with created sources list and count, or error.

    Raises:
        HTTPException: 400 for duplicate URLs or invalid data; 500 for failures.

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
