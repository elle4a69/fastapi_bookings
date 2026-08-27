from prometheus_client import Counter, Gauge, Histogram


HTTP_REQUESTS_TOTAL = Counter(
    "url_shortener_http_requests_total",
    "Total HTTP requests.",
    ("method", "route", "status_code"),
)
HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "url_shortener_http_request_duration_seconds",
    "HTTP request duration in seconds.",
    ("method", "route"),
)
HTTP_REQUESTS_IN_PROGRESS = Gauge(
    "url_shortener_http_requests_in_progress",
    "HTTP requests currently being processed.",
)
REQUEST_BODY_REJECTIONS_TOTAL = Counter(
    "url_shortener_request_body_rejections_total",
    "Requests rejected because the body exceeded the configured limit.",
)
BATCH_ITEMS_TOTAL = Counter(
    "url_shortener_batch_items_total",
    "Batch URL items grouped by outcome.",
    ("status",),
)
