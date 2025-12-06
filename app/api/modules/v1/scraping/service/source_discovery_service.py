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
    """Orchestrates the discovery, filtering, and validation of data sources.

    This service combines Generative AI (Gemini) for reasoning and query generation
    with an external Search API (Tavily) to find and verify relevant websites.

    It treats the Jurisdiction as the authoritative boundary but allows for broader
    source discovery (not limited to government sites), validating relevance and recency.
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
        jurisdiction_prompt: Optional[str] = None,
        project_description: str = "",
        search_query: Optional[str] = None,
    ) -> List[SuggestedSource]:
        """Discover and validate sources based on context and user input.

        This method executes a pipeline:
        1. Generates targeted search queries (Official + Reputable Third-Party).
        2. Executes searches against the live web.
        3. Filters results for relevance, directness (deep links), and recency.
        4. Validates that the URLs are reachable.

        Args:
            jurisdiction_name (str): The name of the jurisdiction (e.g., 'United Kingdom').
            jurisdiction_description (Optional[str]): Detailed context about the jurisdiction.
            jurisdiction_prompt (Optional[str]): AI guidance for extraction or
                classification tasks (e.g., 'Focus on crypto guidelines').
            project_description (str): The monitoring goal (used as context).
            search_query (Optional[str]): Specific user input to narrow the search.

        Returns:
            List[SuggestedSource]: A list of validated source candidates.
        """
        search_queries = await self._generate_search_queries(
            jurisdiction_name,
            jurisdiction_description,
            jurisdiction_prompt,
            project_description,
            search_query,
        )

        raw_results = await self._execute_search(search_queries)

        suggested_sources = await self._analyze_and_filter_results(
            raw_results, jurisdiction_name, jurisdiction_prompt, project_description, search_query
        )

        valid_sources = await self._validate_urls(suggested_sources)

        return valid_sources

    async def _generate_search_queries(
        self,
        jurisdiction_name: str,
        jurisdiction_desc: Optional[str],
        jurisdiction_prompt: Optional[str],
        project_desc: str,
        user_query: Optional[str],
    ) -> List[str]:
        """Generate targeted search queries to find diverse, relevant sources.

        Args:
            jurisdiction_name (str): The name of the jurisdiction.
            jurisdiction_desc (Optional[str]): Description of the jurisdiction.
            jurisdiction_prompt (Optional[str]): AI guidance for extraction or classification tasks.
            project_desc (str): The user's monitoring goal.
            user_query (Optional[str]): Specific input from the user.

        Returns:
            List[str]: A list of search query strings.
        """
        jurisdiction_context = jurisdiction_name
        if jurisdiction_desc:
            jurisdiction_context += f" ({jurisdiction_desc})"

        # Build jurisdiction guidance section
        jurisdiction_guidance = ""
        if jurisdiction_prompt:
            jurisdiction_guidance = (
                f'\nJURISDICTION GUIDANCE (AI Extraction Focus): "{jurisdiction_prompt}"'
            )

        if user_query:
            task_instruction = (
                f"Generate 5 targeted search queries to find varied sources for '{user_query}' "
                f"relevant to the jurisdiction: '{jurisdiction_context}'.\n"
                "- Include queries for official government announcements.\n"
                "- Include queries for reputable industry news or legal analysis pages.\n"
                "- Focus on finding 'latest' or 'current' information pages.\n"
                "- Ensure the queries explicitly include the jurisdiction name."
            )
        else:
            task_instruction = (
                f"Generate 5 specific search queries to find high-quality information sources "
                f"for monitoring '{project_desc}' in '{jurisdiction_context}'.\n"
                "- Target official gazettes, regulatory bodies, AND reputable news/analysis hubs.\n"
                "- Prioritize queries that look for 'updates', 'news', or 'latest regulations'."
            )

        prompt = f"""
        You are an Expert Web Researcher.
        
        PRIMARY BOUNDARY (Jurisdiction): "{jurisdiction_context}"{jurisdiction_guidance}
        CONTEXT (Project Goal): "{project_desc}"
        
        TASK:
        {task_instruction}
        
        Output strictly a JSON list of strings.
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

        # Increase query limit to get more raw results (up to 4 queries)
        for query in queries[:4]:
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
        self,
        search_results: List[Dict],
        jurisdiction_name: str,
        jurisdiction_prompt: Optional[str],
        intent: str,
        user_query: Optional[str],
    ) -> List[SuggestedSource]:
        """Filter results for relevance, deep links, and quality (Official & Unofficial).

        Args:
            search_results (List[Dict]): Raw results from the search API.
            jurisdiction_name (str): The target jurisdiction.
            jurisdiction_prompt (Optional[str]): AI guidance for extraction or classification tasks.
            intent (str): The monitoring intent.
            user_query (Optional[str]): The specific user search input.

        Returns:
            List[SuggestedSource]: A list of sources filtered by the LLM.
        """
        # Deduplicate by URL
        unique_results = {res["url"]: res for res in search_results}.values()

        specific_intent = user_query if user_query else intent

        # Build jurisdiction guidance section
        jurisdiction_guidance = ""
        if jurisdiction_prompt:
            jurisdiction_guidance = (
                f'\nJURISDICTION GUIDANCE (AI Extraction Focus): "{jurisdiction_prompt}"'
            )

        prompt = f"""
        I have a list of search results. I need to identify VALID, HIGH-QUALITY sources for the
        Jurisdiction: "{jurisdiction_name}"{jurisdiction_guidance}
        
        We are looking for sources relevant to: "{specific_intent}"
        
        Search Results:
        {json.dumps(list(unique_results))}
        
        Task:
        1. Select ALL high-quality sources (Official Government sites AND
           reputable Industry/Legal news).
        2. FILTER OUT:
           - Broken or low-quality spam blogs.
           - Generic "Table of Contents" or "Landing Pages" if a direct content page is available.
           - Sources unrelated to "{jurisdiction_name}".
        3. PRIORITIZE:
           - "Deep Links" that contain the actual information
             (e.g., a specific regulation page vs. a homepage).
           - Recent or frequently updated pages.
           - Sources that align with the jurisdiction guidance above, if provided.
        4. Determine `is_official`: true for government/regulatory bodies,
           false for news/blogs/firms.
        5. Return as many valid options as found.
        
        JSON Schema:
        [
          {{
            "title": "Page Title",
            "url": "https://...",
            "snippet": "Description...",
            "confidence_reason": "Why is this a good source? e.g. 'Direct link to "
            "2024 regulations'",
            "is_official": boolean
          }}
        ]
        """

        response = await self.llm.generate_content_async(
            prompt, generation_config={"response_mime_type": "application/json"}
        )

        parsed = json.loads(response.text)
        return [SuggestedSource(**item) for item in parsed]

    async def _validate_urls(self, sources: List[SuggestedSource]) -> List[SuggestedSource]:
        """Verify that the suggested source URLs are reachable.

        Args:
            sources (List[SuggestedSource]): The list of potential sources.

        Returns:
            List[SuggestedSource]: The list of sources that returned a successful HTTP status.
        """
        valid_sources = []
        for source in sources:
            try:
                # Use a standard browser User-Agent to avoid immediate blocking
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 "
                    "Safari/537.36"
                }

                # Try HEAD first
                try:
                    resp = await self.http_client.head(
                        source.url, follow_redirects=True, timeout=5.0, headers=headers
                    )
                    if resp.status_code < 400:
                        valid_sources.append(source)
                        continue
                except Exception:
                    pass  # HEAD failed, fallback to GET

                # Fallback to GET if HEAD fails or isn't allowed
                resp = await self.http_client.get(
                    source.url, follow_redirects=True, timeout=8.0, headers=headers
                )
                if resp.status_code < 400:
                    valid_sources.append(source)
            except Exception:
                logger.warning(f"Discarding unreachable URL: {source.url}")

        return valid_sources
