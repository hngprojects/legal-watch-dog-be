import time
from collections import defaultdict
from typing import Callable

from fastapi import HTTPException, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware that limits requests to a specified number per minute.
    Excludes certain paths from rate limiting (e.g., waitlist endpoints).
    """

    def __init__(
        self,
        app,
        requests_per_minute: int = 50,
        excluded_paths: list[str] | None = None,
    ):
        """
        Initialize the rate limit middleware.

        Args:
            app: The FastAPI application instance.
            requests_per_minute: Maximum number of requests allowed per minute per client IP.
            excluded_paths: List of path prefixes to exclude from rate limiting.
        """
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.excluded_paths = excluded_paths or []
        self.request_logs: dict[str, list[float]] = defaultdict(list)

    def _is_excluded_path(self, path: str) -> bool:
        """
        Check if the path is excluded from rate limiting.

        Args:
            path: The request path to check.

        Returns:
            True if the path should be excluded from rate limiting, False otherwise.
        """
        for excluded_path in self.excluded_paths:
            if path.startswith(excluded_path):
                return True
        return False

    def _clean_old_requests(self, client_ip: str, current_time: float) -> None:
        """
        Remove requests older than 1 minute from the request log.

        Args:
            client_ip: The client IP address.
            current_time: The current timestamp in seconds.
        """
        one_minute_ago = current_time - 60
        self.request_logs[client_ip] = [
            timestamp
            for timestamp in self.request_logs[client_ip]
            if timestamp > one_minute_ago
        ]

    def _get_client_ip(self, request: Request) -> str:
        """
        Extract client IP address from request.

        Checks the following headers in order:
        1. X-Forwarded-For (for proxy/load balancer scenarios)
        2. X-Real-IP
        3. Direct client IP from request

        Args:
            request: The FastAPI request object.

        Returns:
            The client IP address as a string.
        """
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        return request.client.host if request.client else "unknown"

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process the request and apply rate limiting.

        Args:
            request: The incoming request.
            call_next: The next middleware or route handler.

        Returns:
            The response with rate limit headers added.

        Raises:
            HTTPException: 429 status code if rate limit is exceeded.
        """
        if self._is_excluded_path(request.url.path):
            return await call_next(request)

        client_ip = self._get_client_ip(request)
        current_time = time.time()

        self._clean_old_requests(client_ip, current_time)

        if len(self.request_logs[client_ip]) >= self.requests_per_minute:
            oldest_request = min(self.request_logs[client_ip])
            reset_time = int(oldest_request + 60 - current_time)

            raise HTTPException(
                status_code=429,
                detail={
                    "status": "failure",
                    "status_code": 429,
                    "message": f"Rate limit exceeded. Maximum {self.requests_per_minute} requests per minute allowed.",
                    "error": {"retry_after": reset_time},
                },
            )

        self.request_logs[client_ip].append(current_time)

        response = await call_next(request)

        remaining = self.requests_per_minute - len(self.request_logs[client_ip])
        response.headers["X-RateLimit-Limit"] = str(self.requests_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(int(current_time + 60))

        return response
