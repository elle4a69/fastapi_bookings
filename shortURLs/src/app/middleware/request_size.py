from starlette.responses import JSONResponse

from app.core.metrics import REQUEST_BODY_REJECTIONS_TOTAL


class _BodyLimitState:
    def __init__(self, receive, send, max_body_bytes: int):
        self.receive = receive
        self.send = send
        self.max_body_bytes = max_body_bytes
        self.received_bytes = 0
        self.response_started = False
        self.body_too_large = False

    async def receive_limited(self):
        message = await self.receive()
        if message["type"] != "http.request":
            return message
        self.received_bytes += len(message.get("body", b""))
        if self.received_bytes > self.max_body_bytes:
            self.body_too_large = True
            return {"type": "http.disconnect"}
        return message

    async def send_tracked(self, message):
        if self.body_too_large:
            return
        if message["type"] == "http.response.start":
            self.response_started = True
        await self.send(message)


class RequestBodyLimitMiddleware:
    def __init__(self, app, max_body_bytes: int):
        self.app = app
        self.max_body_bytes = max_body_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        if self._content_length_exceeds_limit(scope):
            await self._reject(scope, receive, send)
            return

        state = _BodyLimitState(receive, send, self.max_body_bytes)
        await self.app(scope, state.receive_limited, state.send_tracked)
        if state.body_too_large and not state.response_started:
            await self._reject(scope, receive, send)

    def _content_length_exceeds_limit(self, scope) -> bool:
        content_length = dict(scope.get("headers", [])).get(b"content-length")
        if not content_length:
            return False
        try:
            return int(content_length) > self.max_body_bytes
        except ValueError:
            return False

    @staticmethod
    async def _reject(scope, receive, send):
        REQUEST_BODY_REJECTIONS_TOTAL.inc()
        response = JSONResponse(
            status_code=413,
            content={"detail": "Request body is too large."},
        )
        await response(scope, receive, send)
