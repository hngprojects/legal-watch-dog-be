import json

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import to_tsquery
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.api.modules.v1.scraping.models.data_revision import DataRevision
from app.api.modules.v1.search.schemas.search_schema import (
    DataRevisionSearchResult,
    SearchOperator,
    SearchRequest,
    SearchResponse,
)


class SearchService:
    """Service for performing full-text search on DataRevision entities."""

    def __init__(self, db: AsyncSession):
        """
        Initialize the search service.

        Args:
            db: Async database session
        """
        self.db = db

    async def search(self, search_request: SearchRequest) -> SearchResponse:
        """
        Perform full-text search on data revisions.

        Args:
            search_request: Search parameters including query, filters, and pagination

        Returns:
            SearchResponse: Paginated search results with relevance scores
        """
        tsquery = self._build_tsquery(search_request.query, search_request.operator)

        relevance_score_col = func.ts_rank(
            DataRevision.search_vector, to_tsquery("english", tsquery)
        ).label("relevance_score")

        statement = select(
            DataRevision,
            relevance_score_col,
        ).filter(DataRevision.search_vector.op("@@")(to_tsquery("english", tsquery)))

        statement = self._apply_filters(statement, search_request)

        count_statement = select(func.count()).filter(
            DataRevision.search_vector.op("@@")(to_tsquery("english", tsquery))
        )
        count_statement = self._apply_filters(count_statement, search_request)
        count_result = await self.db.execute(count_statement)
        total_count_value = count_result.scalar()
        total_count = total_count_value if total_count_value is not None else 0

        # Calculate pagination
        offset = (search_request.page - 1) * search_request.limit
        total_pages = (total_count + search_request.limit - 1) // search_request.limit

        statement = (
            statement.order_by(relevance_score_col.desc())
            .filter(relevance_score_col >= search_request.min_rank)
            .offset(offset)
            .limit(search_request.limit)
        )
        results_result = await self.db.execute(statement)
        results = results_result.all()

        search_results = [
            DataRevisionSearchResult(
                id=result.DataRevision.id,
                title=result.DataRevision.minio_object_key,
                summary=result.DataRevision.ai_summary,
                content=None,
                key_fields=result.DataRevision.extracted_data or {},
                revision_date=result.DataRevision.scraped_at,
                relevance_score=result.relevance_score,
            )
            for result in results
        ]

        return SearchResponse(
            results=search_results,
            total=total_count,
            page=search_request.page,
            limit=search_request.limit,
            total_pages=total_pages,
            query=search_request.query,
            operator=search_request.operator,
        )

    def _build_tsquery(self, query: str, operator: SearchOperator) -> str:
        """
        Build a PostgreSQL tsquery string from the search query.

        Args:
            query: Raw search query string
            operator: Search operator (AND, OR, NOT, PHRASE)

        Returns:
            str: Formatted tsquery string for PostgreSQL
        """
        query = query.strip()

        if operator == SearchOperator.AND:
            terms = [term for term in query.split() if term]
            tsquery = " & ".join(terms)
        elif operator == SearchOperator.OR:
            terms = [term for term in query.split() if term]
            tsquery = " | ".join(terms)
        elif operator == SearchOperator.NOT:
            terms = [term for term in query.split() if term]
            if not terms:
                tsquery = ""
            elif len(terms) == 1:
                tsquery = f"!{terms[0]}"
            else:
                tsquery = f"{terms[0]} & !({' | '.join(terms[1:])})"
        else:
            tsquery = query

        return tsquery

    def _apply_filters(self, query, search_request: SearchRequest):
        """
        Apply filters to the search query.

        Args:
            query: SQLAlchemy select statement
            search_request: Search request containing filter parameters

        Returns:
            Modified select statement with applied filters
        """
        for key, value in search_request.extracted_data_filters.items():
            if isinstance(value, (dict, list)):
                value_str = json.dumps(value, separators=(",", ":"))
            else:
                value_str = str(value)
            query = query.filter(DataRevision.extracted_data.op("->>")(key) == value_str)

        return query
