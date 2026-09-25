"""Tests for CalComAdapter service."""

from datetime import datetime, timezone
import pytest
import httpx

from app.services.scheduling.calcom_adapter import CalComAdapter


@pytest.mark.asyncio
async def test_calcom_get_available_slots_grouped_format():
    """Test retrieving slots when Cal.com returns grouped dates dict."""
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert "/slots" in request.url.path
        assert request.url.params["eventTypeId"] == "123"
        assert request.url.params["timeZone"] == "America/New_York"
        data = {
            "slots": {
                "2026-09-10": [
                    {"time": "2026-09-10T14:00:00.000Z"},
                    {"time": "2026-09-10T15:00:00.000Z"},
                ],
                "2026-09-11": [
                    {"time": "2026-09-11T10:00:00.000Z"}
                ]
            }
        }
        return httpx.Response(200, json=data)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        adapter = CalComAdapter(api_key="test_key", base_url="https://api.cal.com/v1", client=client)
        slots = await adapter.get_available_slots(
            event_type_id=123,
            start_time=datetime(2026, 9, 10, 0, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 9, 12, 0, 0, tzinfo=timezone.utc),
            time_zone="America/New_York",
        )

        assert len(slots) == 3
        times = [s["time"] for s in slots]
        assert "2026-09-10T14:00:00.000Z" in times
        assert "2026-09-11T10:00:00.000Z" in times


@pytest.mark.asyncio
async def test_calcom_get_available_slots_flat_list():
    """Test retrieving slots when Cal.com returns a flat list."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"slots": [{"time": "2026-09-10T16:00:00.000Z"}]})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        adapter = CalComAdapter(api_key="test_key", client=client)
        slots = await adapter.get_available_slots(
            event_type_id=456,
            start_time=datetime(2026, 9, 10, 0, 0),
            end_time=datetime(2026, 9, 10, 23, 59),
        )
        assert len(slots) == 1
        assert slots[0]["time"] == "2026-09-10T16:00:00.000Z"


@pytest.mark.asyncio
async def test_calcom_get_available_slots_timeout_fallback():
    """Test timeout during slot retrieval returns empty list gracefully."""
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("Connection timed out", request=request)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        adapter = CalComAdapter(client=client)
        slots = await adapter.get_available_slots(
            event_type_id=999,
            start_time=datetime(2026, 9, 10, 0, 0),
            end_time=datetime(2026, 9, 10, 23, 59),
        )
        assert slots == []


@pytest.mark.asyncio
async def test_calcom_get_available_slots_error_fallback():
    """Test 500 server error returns empty list gracefully."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="Internal Server Error")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        adapter = CalComAdapter(client=client)
        slots = await adapter.get_available_slots(
            event_type_id=999,
            start_time=datetime(2026, 9, 10, 0, 0),
            end_time=datetime(2026, 9, 10, 23, 59),
        )
        assert slots == []


@pytest.mark.asyncio
async def test_calcom_create_booking_hold_success():
    """Test successfully placing a booking hold."""
    captured_payload = {}

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_payload
        import json
        assert request.method == "POST"
        assert "/bookings" in request.url.path
        captured_payload = json.loads(request.content)
        return httpx.Response(201, json={"id": 888, "status": "PENDING", "title": "Hold for Alice"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        adapter = CalComAdapter(api_key="secret", client=client)
        start = datetime(2026, 9, 10, 10, 0)
        result = await adapter.create_booking_hold(
            event_type_id=42,
            start_time=start,
            client_name="Alice Smith",
            client_email="alice@example.com",
            notes="Please prepare room A",
        )

        assert result["id"] == 888
        assert result["status"] == "PENDING"
        assert captured_payload["eventTypeId"] == 42
        assert captured_payload["name"] == "Alice Smith"
        assert captured_payload["email"] == "alice@example.com"
        assert captured_payload["notes"] == "Please prepare room A"
        assert captured_payload["metadata"]["is_hold"] is True


@pytest.mark.asyncio
async def test_calcom_create_booking_hold_failure():
    """Test create_booking_hold fallback on server error."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, text="Invalid slot time")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        adapter = CalComAdapter(client=client)
        result = await adapter.create_booking_hold(
            event_type_id=42,
            start_time=datetime(2026, 9, 10, 10, 0),
            client_name="Alice Smith",
            client_email="alice@example.com",
        )
        assert result["status"] == "error"
        assert result["error_type"] == "http_error"
        assert result["status_code"] == 400


@pytest.mark.asyncio
async def test_calcom_confirm_booking_patch():
    """Test confirming a booking with PATCH."""
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "PATCH"
        assert "/bookings/888" in request.url.path
        return httpx.Response(200, json={"id": 888, "status": "ACCEPTED"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        adapter = CalComAdapter(client=client)
        result = await adapter.confirm_booking(888)
        assert result["id"] == 888
        assert result["status"] == "ACCEPTED"


@pytest.mark.asyncio
async def test_calcom_confirm_booking_fallback_to_post():
    """Test confirming booking falls back to POST /confirm if PATCH is 405."""
    call_counts = {"PATCH": 0, "POST": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "PATCH":
            call_counts["PATCH"] += 1
            return httpx.Response(405, text="Method Not Allowed")
        elif request.method == "POST":
            call_counts["POST"] += 1
            assert "/bookings/888/confirm" in request.url.path
            return httpx.Response(200, json={"id": 888, "status": "ACCEPTED"})
        return httpx.Response(400)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        adapter = CalComAdapter(client=client)
        result = await adapter.confirm_booking(888)
        assert call_counts["PATCH"] == 1
        assert call_counts["POST"] == 1
        assert result["status"] == "ACCEPTED"


@pytest.mark.asyncio
async def test_calcom_confirm_booking_error():
    """Test confirming booking handles timeout."""
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("Timeout", request=request)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        adapter = CalComAdapter(client=client)
        result = await adapter.confirm_booking("invalid_id")
        assert result["status"] == "error"
        assert result["error_type"] == "timeout"


@pytest.mark.asyncio
async def test_calcom_rate_limit_429():
    """Test handling of HTTP 429 Rate Limit across adapter methods."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, text="Too Many Requests")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        adapter = CalComAdapter(client=client)

        # 1. get_available_slots returns empty list on 429
        slots = await adapter.get_available_slots(
            event_type_id=1,
            start_time=datetime(2026, 9, 10, 0, 0),
            end_time=datetime(2026, 9, 10, 23, 59),
        )
        assert slots == []

        # 2. create_booking_hold returns structured error with 429 status code
        hold = await adapter.create_booking_hold(
            event_type_id=1,
            start_time=datetime(2026, 9, 10, 10, 0),
            client_name="Rate Limited User",
            client_email="rl@example.com",
        )
        assert hold["status"] == "error"
        assert hold["error_type"] == "http_error"
        assert hold["status_code"] == 429

        # 3. confirm_booking returns structured error with 429 status code
        confirm = await adapter.confirm_booking(booking_id=123)
        assert confirm["status"] == "error"
        assert confirm["error_type"] == "http_error"
        assert confirm["status_code"] == 429


@pytest.mark.asyncio
async def test_calcom_server_errors_500():
    """Test 500 server errors for create_booking_hold and confirm_booking."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="Internal Server Error")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        adapter = CalComAdapter(client=client)

        hold = await adapter.create_booking_hold(
            event_type_id=1,
            start_time=datetime(2026, 9, 10, 10, 0),
            client_name="Test User",
            client_email="test@example.com",
        )
        assert hold["status"] == "error"
        assert hold["error_type"] == "http_error"
        assert hold["status_code"] == 500

        confirm = await adapter.confirm_booking(booking_id=456)
        assert confirm["status"] == "error"
        assert confirm["error_type"] == "http_error"
        assert confirm["status_code"] == 500


@pytest.mark.asyncio
async def test_calcom_empty_slots_variations():
    """Test retrieving slots when response contains empty slots data in various shapes."""
    shapes = [
        {"slots": {}},
        {"slots": []},
        {},
        {"slots": None},
        {"slots": {"2026-09-10": []}},
    ]
    for shape in shapes:
        def handler(request: httpx.Request, s=shape) -> httpx.Response:
            return httpx.Response(200, json=s)

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            adapter = CalComAdapter(client=client)
            slots = await adapter.get_available_slots(
                event_type_id=1,
                start_time=datetime(2026, 9, 10, 0, 0),
                end_time=datetime(2026, 9, 10, 23, 59),
            )
            assert slots == []


@pytest.mark.asyncio
async def test_calcom_malformed_json():
    """Test handling of malformed or non-JSON response from Cal.com."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html><body>502 Bad Gateway Nginx</body></html>")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        adapter = CalComAdapter(client=client)

        # Slot query should gracefully catch JSON decode error and return []
        slots = await adapter.get_available_slots(
            event_type_id=1,
            start_time=datetime(2026, 9, 10, 0, 0),
            end_time=datetime(2026, 9, 10, 23, 59),
        )
        assert slots == []

        # Hold creation should return unexpected_error dict
        hold = await adapter.create_booking_hold(
            event_type_id=1,
            start_time=datetime(2026, 9, 10, 10, 0),
            client_name="Malformed User",
            client_email="m@example.com",
        )
        assert hold["status"] == "error"
        assert hold["error_type"] == "unexpected_error"


@pytest.mark.asyncio
async def test_calcom_string_slots_and_context_manager():
    """Test parsing string slots in grouped and flat responses, and context manager lifecycle."""
    def handler(request: httpx.Request) -> httpx.Response:
        if "grouped" in request.url.params.get("timeZone", ""):
            return httpx.Response(
                200,
                json={"slots": {"2026-09-10": ["2026-09-10T11:00:00.000Z"]}},
            )
        return httpx.Response(
            200,
            json={"slots": ["2026-09-10T12:00:00.000Z"]},
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        async with CalComAdapter(api_key="my_key", client=client) as adapter:
            # Grouped string slot
            slots1 = await adapter.get_available_slots(
                event_type_id=1,
                start_time=datetime(2026, 9, 10, 0, 0),
                end_time=datetime(2026, 9, 10, 23, 59),
                time_zone="grouped",
            )
            assert len(slots1) == 1
            assert slots1[0]["time"] == "2026-09-10T11:00:00.000Z"
            assert slots1[0]["date"] == "2026-09-10"

            # Flat string slot
            slots2 = await adapter.get_available_slots(
                event_type_id=1,
                start_time=datetime(2026, 9, 10, 0, 0),
                end_time=datetime(2026, 9, 10, 23, 59),
                time_zone="flat",
            )
            assert len(slots2) == 1
            assert slots2[0]["time"] == "2026-09-10T12:00:00.000Z"


@pytest.mark.asyncio
async def test_calcom_create_booking_hold_timeout():
    """Test timeout during create_booking_hold."""
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("Hold timeout", request=request)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        adapter = CalComAdapter(client=client)
        hold = await adapter.create_booking_hold(
            event_type_id=1,
            start_time=datetime(2026, 9, 10, 10, 0),
            client_name="Timeout User",
            client_email="to@example.com",
        )
        assert hold["status"] == "error"
        assert hold["error_type"] == "timeout"

