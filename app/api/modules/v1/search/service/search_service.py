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
    def __init__(self, db: AsyncSession):
        self.db = db

    async def search(self, search_request: SearchRequest) -> SearchResponse:
        tsquery = self._build_tsquery(search_request.query, search_request.operator)

        # Define relevance score column once to avoid duplication
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

        statement = (
            statement.order_by(relevance_score_col.desc())
            .filter(relevance_score_col >= search_request.min_rank)
            .offset(search_request.offset)
            .limit(search_request.limit)
        )
        results_result = await self.db.execute(statement)
        results = results_result.all()

        search_results = [
            DataRevisionSearchResult(
                id=result.DataRevision.id,
                title=result.DataRevision.minio_object_key,
                summary=result.DataRevision.ai_summary,
                content=None,  # DataRevision doesn't have content field
                key_fields=result.DataRevision.extracted_data or {},
                revision_date=result.DataRevision.scraped_at,
                relevance_score=result.relevance_score,
            )
            for result in results
        ]

        return SearchResponse(
            results=search_results,
            total_count=total_count,
            query=search_request.query,
            has_more=(search_request.offset + len(search_results)) < total_count,
        )

    def _build_tsquery(self, query: str, operator: SearchOperator) -> str:
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
                tsquery = f"!{terms}"
            else:
                tsquery = f"{terms} & !({' | '.join(terms[1:])})"
        else:
            tsquery = query

        return tsquery

    def _apply_filters(self, query, search_request: SearchRequest):
        # Apply filters for extracted_data
        for key, value in search_request.extracted_data_filters.items():
            # Convert value to string since ->> operator returns text
            if isinstance(value, (dict, list)):
                value_str = json.dumps(value, separators=(",", ":"))
            else:
                value_str = str(value)
            query = query.filter(DataRevision.extracted_data.op("->>")(key) == value_str)

        return query
