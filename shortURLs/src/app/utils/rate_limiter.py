from time import time
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response, JSONResponse
from starlette.requests import Request


class RateLimiter(BaseHTTPMiddleware):

    def __init__(self, app, max_requests: int, period: int):
        super().__init__(app)
        self.max_requests = max_requests
        self.period = period
        self.requests: dict[str, tuple[int, float]] = {}
        self.last_cleanup = time()

    def _get_client_key(self, request: Request) -> str | None:
        client = request.client
        if client and client.host:
            return client.host
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip.strip()
        return None

    def _cleanup(self, current_time: float) -> None:
        if current_time - self.last_cleanup < self.period:
            return
        cutoff = current_time - self.period
        self.requests = {
            client: (count, start_time)
            for client, (count, start_time) in self.requests.items()
            if start_time >= cutoff
        }
        self.last_cleanup = current_time

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        current_time = time()
        self._cleanup(current_time)
        client_key = self._get_client_key(request)
        if not client_key:
            return await call_next(request)

        if client_key not in self.requests:
            self.requests[client_key] = (1, current_time)
        else:
            count, start_time = self.requests[client_key]
            if current_time - start_time < self.period:
                if count >= self.max_requests:
                    return JSONResponse(
                        status_code=429,
                        content={"detail": "请求过于频繁,请稍后再试。"}
                    )
                self.requests[client_key] = (count + 1, start_time)
            else:
                self.requests[client_key] = (1, current_time)

        return await call_next(request)
