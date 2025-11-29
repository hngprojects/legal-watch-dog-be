import asyncio
import json
import logging
from typing import Dict, List, Optional

import google.generativeai as genai
import httpx
from tavily import TavilyClient

from app.api.core.config import settings
from app.api.modules.v1.scraping.schemas.source_discovery_schema import SuggestedSource

logger = logging.getLogger(__name__)


class SourceDiscoveryService:
    """Orchestrates the discovery, filtering, and validation of official data sources.

    This service combines Generative AI (Gemini) for reasoning and query generation
    with an external Search API (Tavily) to find and verify official government
    or regulatory websites.

    It treats the Jurisdiction as the primary entity to discover, using the Project
    intent only for context and filtering.
    """

    def __init__(self):
        """Initialize the SourceDiscoveryService with AI and Search clients.

        Raises:
            ValueError: If TAVILY_API_KEY is not set in the configuration.
        """
        self.llm = genai.GenerativeModel(model_name=settings.MODEL_NAME)
        self.http_client = httpx.AsyncClient(timeout=10.0)

        if not settings.TAVILY_API_KEY:
            raise ValueError("TAVILY_API_KEY is not set in configuration.")
        self.tavily_client = TavilyClient(api_key=settings.TAVILY_API_KEY)

    async def suggest_sources(
        self,
        jurisdiction_name: str,
        jurisdiction_description: Optional[str],
        project_description: str,
    ) -> List[SuggestedSource]:
        """Discover and validate official sources for a specific jurisdiction.

        This method executes a pipeline:
        1. Generates search queries focused on finding the Jurisdiction's official body/repository.
        2. Executes searches against the live web.
        3. Filters results for official domains, using the project description to ensure relevance.
        4. Validates that the URLs are reachable.

        Args:
            jurisdiction_name (str): The name of the jurisdiction (e.g., 'United Kingdom', 'GDPR').
            jurisdiction_description (Optional[str]): Detailed context about the jurisdiction.
            project_description (str): The monitoring goal (used as context).

        Returns:
            List[SuggestedSource]: A list of validated, official source candidates.
        """
        search_queries = await self._generate_search_queries(
            jurisdiction_name, jurisdiction_description, project_description
        )

        raw_results = await self._execute_search(search_queries)

        suggested_sources = await self._analyze_and_filter_results(
            raw_results, jurisdiction_name, project_description
        )

        valid_sources = await self._validate_urls(suggested_sources)

        return valid_sources

    async def _generate_search_queries(
        self, jurisdiction_name: str, jurisdiction_desc: Optional[str], project_desc: str
    ) -> List[str]:
        """Generate targeted search queries to find the Jurisdiction's official sources.

        Args:
            jurisdiction_name (str): The name of the jurisdiction.
            jurisdiction_desc (str): Description of the jurisdiction.
            project_desc (str): The user's monitoring goal.

        Returns:
            List[str]: A list of search query strings.
        """
        jurisdiction_context = jurisdiction_name
        if jurisdiction_desc:
            jurisdiction_context += f" ({jurisdiction_desc})"

        prompt = f"""
        You are an expert Legal Researcher.
        
        PRIMARY OBJECTIVE: Find the OFFICIAL website, gazette, or repository for this Jurisdiction:
        "{jurisdiction_context}"
        
        CONTEXT (User's Goal): The user wants to monitor this jurisdiction for:
        "{project_desc}"
        
        Task:
        Generate 3 specific search queries to find the official home page or legislation
        repository for this Jurisdiction.
        - Focus on finding the *source* (the authority), not just a news article about the topic.
        - If the jurisdiction is a body (e.g., "NIST"), look for their standards page.
        - If the jurisdiction is a country/state, look for their official gazette or department
        related to the context.        Output strictly a JSON list of strings.
        """
        response = await self.llm.generate_content_async(
            prompt, generation_config={"response_mime_type": "application/json"}
        )
        return json.loads(response.text)

    async def _execute_search(self, queries: List[str]) -> List[Dict]:
        """Execute search queries using the Tavily API.

        Args:
            queries (List[str]): The list of search queries to execute.

        Returns:
            List[Dict]: A consolidated list of search results.
        """
        aggregated_results = []

        for query in queries[:2]:
            try:
                response = await asyncio.to_thread(
                    self.tavily_client.search,
                    query=query,
                    search_depth="basic",
                    max_results=5,
                    include_domains=[],
                )

                if "results" in response:
                    aggregated_results.extend(response["results"])
            except Exception as e:
                logger.error(f"Search API failed for query '{query}': {e}")

        return aggregated_results

    async def _analyze_and_filter_results(
        self, search_results: List[Dict], jurisdiction_name: str, intent: str
    ) -> List[SuggestedSource]:
        """Filter search results to identify only official sources for the Jurisdiction.

        Args:
            search_results (List[Dict]): Raw results from the search API.
            jurisdiction_name (str): The target jurisdiction.
            intent (str): The monitoring intent.

        Returns:
            List[SuggestedSource]: A list of sources deemed 'official' by the LLM.
        """
        unique_results = {res["url"]: res for res in search_results}.values()

        prompt = f"""
        I have a list of search results. I need to identify the OFFICIAL source(s) for the
        Jurisdiction: "{jurisdiction_name}"
        
        The user intends to monitor: "{intent}"
        
        Search Results:
        {json.dumps(list(unique_results))}
        
        Task:
        1. Identify which URLs belong to the OFFICIAL authority for "{jurisdiction_name}".
        2. Discard news articles, blogs, or third-party summaries.
        3. Return a JSON list of the best candidates.
        
        JSON Schema:
        [
          {{
            "title": "Page Title",
            "url": "https://...",
            "snippet": "Description...",
            "confidence_reason": "Why is this valid? e.g. 'It is the official site of "
            f"[{jurisdiction_name}]'",
            "is_official": true
          }}
        ]
        """

        response = await self.llm.generate_content_async(
            prompt, generation_config={"response_mime_type": "application/json"}
        )

        parsed = json.loads(response.text)
        return [SuggestedSource(**item) for item in parsed if item.get("is_official")]

    async def _validate_urls(self, sources: List[SuggestedSource]) -> List[SuggestedSource]:
        """Verify that the suggested source URLs are reachable."""
        valid_sources = []
        for source in sources:
            try:
                resp = await self.http_client.head(source.url, follow_redirects=True, timeout=3.0)
                if resp.status_code < 400:
                    valid_sources.append(source)
            except Exception:
                try:
                    resp = await self.http_client.get(
                        source.url, follow_redirects=True, timeout=5.0
                    )
                    if resp.status_code < 400:
                        valid_sources.append(source)
                except Exception:
                    logger.warning(f"Discarding dead URL: {source.url}")
        return valid_sources
