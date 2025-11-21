import logging
import time
import uuid
from typing import Callable

from fastapi import Request
from fastapi.responses import JSONResponse, Response
from redis.exceptions import RedisError
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.core.dependencies.redis_service import get_redis_client

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Redis-based rate limiting middleware that limits requests to a specified number per minute.

    Uses Redis for distributed rate limiting, making it suitable for multi-server deployments.
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
        Process the request and apply rate limiting using Redis.

        Uses Redis sorted sets to track requests with timestamps as scores.
        Automatically removes expired entries older than 60 seconds.

        Args:
            request: The incoming request.
            call_next: The next middleware or route handler.

        Returns:
            JSONResponse with 429 status code if rate limit is exceeded,
            or the response from the next handler with rate limit headers added.
        """
        if self._is_excluded_path(request.url.path):
            return await call_next(request)

        client_ip = self._get_client_ip(request)
        current_time = time.time()
        redis_key = f"rate_limit:api:{client_ip}"

        try:
            redis_client = await get_redis_client()

            one_minute_ago = current_time - 60
            await redis_client.zremrangebyscore(redis_key, 0, one_minute_ago)

            request_count = await redis_client.zcard(redis_key)

            if request_count >= self.requests_per_minute:
                oldest_request = await redis_client.zrange(redis_key, 0, 0, withscores=True)
                if oldest_request:
                    oldest_timestamp = oldest_request[0][1]
                    reset_time = int(oldest_timestamp + 60 - current_time)
                else:
                    reset_time = 60

                return JSONResponse(
                    status_code=429,
                    content={
                        "status": "failure",
                        "status_code": 429,
                        "message": (
                            f"Rate limit exceeded. Maximum {self.requests_per_minute} "
                            "requests per minute allowed."
                        ),
                        "error": {"retry_after": reset_time},
                    },
                )

            # Use unique ID with timestamp as score to avoid collisions
            member = f"{current_time}:{uuid.uuid4()}"
            await redis_client.zadd(redis_key, {member: current_time})
            await redis_client.expire(redis_key, 60)

            response = await call_next(request)

            # Get the oldest request timestamp to calculate reset time
            oldest_request = await redis_client.zrange(redis_key, 0, 0, withscores=True)
            if oldest_request:
                oldest_timestamp = oldest_request[0][1]
                reset_timestamp = int(oldest_timestamp + 60)
            else:
                reset_timestamp = int(current_time + 60)

            request_count = await redis_client.zcard(redis_key)
            remaining = self.requests_per_minute - request_count
            response.headers["X-RateLimit-Limit"] = str(self.requests_per_minute)
            response.headers["X-RateLimit-Remaining"] = str(remaining)
            response.headers["X-RateLimit-Reset"] = str(reset_timestamp)

            return response

        except RedisError as e:
            logger.error(f"Redis error in rate limiter: {e}")
            response = await call_next(request)
            return response
