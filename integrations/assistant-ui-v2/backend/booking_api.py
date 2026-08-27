"""HTTP adapter for the authoritative FastAPI Bookings application.

The Assistant UI deliberately consumes the booking application through its
published API.  No booking database models are imported here.
"""

from __future__ import annotations

import os
import time
from datetime import datetime, timedelta
from typing import Any, Optional
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import requests


class BookingApiError(RuntimeError):
    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class BookingApiClient:
    """Small compatibility client used by the Assistant UI booking screens."""

    def __init__(
        self,
        base_url: str,
        *,
        tenant: str = "",
        token: str = "",
        timeout: float = 10.0,
        default_service_id: Optional[int] = None,
        default_provider_id: Optional[int] = None,
        default_location_id: Optional[int] = None,
        availability_days: int = 7,
        auto_confirm: bool = True,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.tenant = tenant.strip()
        self.token = token.strip()
        self.timeout = timeout
        self.default_service_id = default_service_id
        self.default_provider_id = default_provider_id
        self.default_location_id = default_location_id
        self.availability_days = max(1, min(availability_days, 10))
        self.auto_confirm = auto_confirm
        self._bootstrap_cache: tuple[float, dict[str, Any]] | None = None
        self._admin_services_cache: tuple[float, list[dict[str, Any]]] | None = None

    @classmethod
    def from_env(cls) -> "BookingApiClient":
        base_url = os.getenv("BOOKING_API_BASE_URL", "http://127.0.0.1:8000")
        token = os.getenv("BOOKING_API_TOKEN")
        if token is None and urlparse(base_url).hostname in {"127.0.0.1", "localhost"}:
            token = "mock-admin-token"
        return cls(
            base_url,
            tenant=os.getenv("BOOKING_API_TENANT", ""),
            token=token or "",
            timeout=float(os.getenv("BOOKING_API_TIMEOUT_SECONDS", "30")),
            default_service_id=_optional_int(os.getenv("BOOKING_API_DEFAULT_SERVICE_ID")),
            default_provider_id=_optional_int(os.getenv("BOOKING_API_DEFAULT_PROVIDER_ID")),
            default_location_id=_optional_int(os.getenv("BOOKING_API_DEFAULT_LOCATION_ID")),
            availability_days=int(os.getenv("BOOKING_API_AVAILABILITY_DAYS", "7")),
            auto_confirm=_env_bool("BOOKING_API_AUTO_CONFIRM", True),
        )

    def _headers(self, *, admin: bool = False) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.tenant:
            headers["X-Tenant"] = self.tenant
        if admin:
            if not self.token:
                raise BookingApiError(
                    "Booking administration requires BOOKING_API_TOKEN.",
                    status_code=503,
                )
            headers["X-Token"] = self.token
        return headers

    def _request(
        self,
        method: str,
        path: str,
        *,
        admin: bool = False,
        params: Optional[dict[str, Any]] = None,
        json: Optional[dict[str, Any]] = None,
    ) -> Any:
        try:
            response = requests.request(
                method,
                f"{self.base_url}{path}",
                headers=self._headers(admin=admin),
                params=params,
                json=json,
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise BookingApiError(f"Booking API is unavailable: {exc}", status_code=503) from exc

        try:
            payload = response.json()
        except ValueError:
            payload = None
        if not response.ok:
            message = _error_message(payload) or response.text or response.reason
            raise BookingApiError(
                f"Booking API rejected the request ({response.status_code}): {message}",
                status_code=response.status_code,
            )
        return payload

    def health(self) -> dict[str, Any]:
        return self._request("GET", "/health")

    def bootstrap(self, *, refresh: bool = False) -> dict[str, Any]:
        now = time.monotonic()
        if not refresh and self._bootstrap_cache and now - self._bootstrap_cache[0] < 30:
            return self._bootstrap_cache[1]
        payload = self._request("GET", "/api/public/bootstrap")
        data = payload.get("data", {}) if isinstance(payload, dict) else {}
        self._bootstrap_cache = (now, data)
        return data

    def list_services(self) -> list[dict[str, Any]]:
        services = self.bootstrap().get("services", [])
        return [
            {
                "id": str(service["id"]),
                "name": service.get("name") or "Service",
                "description": service.get("description") or "",
                "price": float(service.get("price") or 0),
                "duration": int(service.get("duration") or 30),
                "showDuration": True,
            }
            for service in services
            if service.get("active", True) and service.get("is_visible", True)
        ]

    def _service(self, service_id: Optional[str | int] = None) -> dict[str, Any]:
        services = self.bootstrap().get("services", [])
        wanted = _optional_int(service_id) or self.default_service_id
        if wanted is not None:
            match = next((item for item in services if int(item.get("id", -1)) == wanted), None)
            if match:
                return self._with_service_relationships(match)
            raise BookingApiError(f"Service {wanted} is not available.", status_code=404)
        if not services:
            raise BookingApiError("The booking system has no active services.", status_code=503)
        return self._with_service_relationships(services[0])

    def _with_service_relationships(self, service: dict[str, Any]) -> dict[str, Any]:
        if not self.token:
            return service
        now = time.monotonic()
        if not self._admin_services_cache or now - self._admin_services_cache[0] >= 30:
            payload = self._request(
                "GET",
                "/api/admin/services",
                admin=True,
                params={"page": 1, "page_size": 100},
            )
            self._admin_services_cache = (now, payload.get("data", []))
        admin_service = next(
            (
                item
                for item in self._admin_services_cache[1]
                if int(item.get("id", -1)) == int(service["id"])
            ),
            None,
        )
        return {**service, **({"provider_ids": admin_service.get("provider_ids", [])} if admin_service else {})}

    def _provider(self, service: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        providers = self.bootstrap().get("providers", [])
        if self.default_provider_id is not None:
            match = next(
                (item for item in providers if int(item.get("id", -1)) == self.default_provider_id),
                None,
            )
            if match:
                return match
            raise BookingApiError(
                f"Configured provider {self.default_provider_id} is not available.",
                status_code=404,
            )
        if not providers:
            raise BookingApiError("The booking system has no active providers.", status_code=503)
        eligible_ids = {
            int(provider_id)
            for provider_id in (service or {}).get("provider_ids", [])
        }
        eligible = [
            provider for provider in providers
            if not eligible_ids or int(provider.get("id", -1)) in eligible_ids
        ]
        if not eligible:
            raise BookingApiError(
                f"No active provider can deliver service {(service or {}).get('id', '')}.",
                status_code=503,
            )
        return max(eligible, key=_provider_schedule_score)

    def _location_id(self) -> Optional[int]:
        if self.default_location_id is not None:
            return self.default_location_id
        locations = self.bootstrap().get("locations", [])
        return int(locations[0]["id"]) if locations else None

    def get_available_slots(
        self,
        service_id: Optional[str | int] = None,
        *,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        service = self._service(service_id)
        provider = self._provider(service)
        bootstrap = self.bootstrap()
        timezone_name = (
            bootstrap.get("timezone")
            or bootstrap.get("tenant", {}).get("timezone")
            or "UTC"
        )
        try:
            timezone = ZoneInfo(timezone_name)
        except Exception:
            timezone = ZoneInfo("UTC")
        start_date = datetime.now(timezone).date()
        slots: list[dict[str, Any]] = []

        for offset in range(self.availability_days):
            date_value = start_date + timedelta(days=offset)
            try:
                payload = self._request(
                    "GET",
                    "/api/public/availability",
                    params={
                        "service_id": int(service["id"]),
                        "provider_id": int(provider["id"]),
                        "date": f"{date_value.isoformat()}T00:00:00",
                    },
                )
            except BookingApiError as exc:
                if exc.status_code == 429 and slots:
                    break
                raise
            for slot in payload.get("data", []):
                slots.append(
                    {
                        "startTime": slot["start"],
                        "endTime": slot["end"],
                        "serviceId": str(service["id"]),
                        "providerId": int(provider["id"]),
                        "locationId": self._location_id(),
                    }
                )
                if len(slots) >= limit:
                    return slots
        return slots

    def _identify_client(self, phone: str, name: str) -> int:
        if not self.token:
            payload = self._request(
                "POST",
                "/api/public/clients",
                json={"name": name, "phone": phone, "active": True},
            )
            return int(payload["data"]["id"])

        payload = self._request(
            "POST",
            "/api/public/clients/identify",
            params={"phone": phone},
        )
        client = payload.get("data", {})
        client_id = int(client["id"])
        if name and client.get("name") != name:
            self._request(
                "PUT",
                f"/api/admin/clients/{client_id}",
                admin=True,
                json={"name": name, "phone": phone},
            )
        return client_id

    def create_booking(
        self,
        *,
        service_id: Optional[str | int],
        name: str,
        phone: str,
        start_time: str | datetime,
        end_time: Optional[str | datetime] = None,
        notes: Optional[str] = None,
        provider_id: Optional[int] = None,
        location_id: Optional[int] = None,
    ) -> dict[str, Any]:
        service = self._service(service_id)
        provider = self._provider(service)
        start = _as_datetime(start_time)
        end = _as_datetime(end_time) if end_time is not None else start + timedelta(
            minutes=int(service.get("duration") or 30)
        )
        client_id = self._identify_client(phone, name)
        booking_payload = {
            "client_id": client_id,
            "provider_id": provider_id or int(provider["id"]),
            "service_id": int(service["id"]),
            "location_id": location_id if location_id is not None else self._location_id(),
            "start_time": start.isoformat(),
            "end_time": end.isoformat(),
            "notes": notes,
        }
        payload = self._request("POST", "/api/public/bookings", json=booking_payload)
        booking = payload.get("data", {})
        if self.auto_confirm and self.token and str(booking.get("status", "")).lower() == "pending":
            confirmed = self._request(
                "POST",
                f"/api/admin/bookings/{booking['id']}/confirm",
                admin=True,
            )
            booking = confirmed.get("data", booking)
        return booking

    def list_bookings(self) -> list[dict[str, Any]]:
        booking_rows: list[dict[str, Any]] = []
        page = 1
        while True:
            payload = self._request(
                "GET",
                "/api/admin/bookings",
                admin=True,
                params={"page": page, "page_size": 100},
            )
            page_rows = payload.get("data", [])
            booking_rows.extend(page_rows)
            meta = payload.get("meta", {})
            total_pages = int(meta.get("pages") or meta.get("total_pages") or 1)
            if page >= total_pages or not page_rows:
                break
            page += 1
        result = []
        for booking in booking_rows:
            client = booking.get("client") or {}
            service = booking.get("service") or {}
            result.append(
                {
                    "id": str(booking["id"]),
                    "customerPhone": client.get("phone") or "",
                    "summary": " - ".join(
                        value for value in (client.get("name"), service.get("name")) if value
                    ) or "Booking",
                    "startTime": booking.get("start_time"),
                    "endTime": booking.get("end_time"),
                    "status": _assistant_status(booking.get("status")),
                    "notes": booking.get("notes") or "",
                }
            )
        return result

    def update_booking(self, booking_id: str | int, changes: dict[str, Any]) -> dict[str, Any]:
        current_payload = self._request(
            "GET", f"/api/admin/bookings/{booking_id}", admin=True
        )
        current = current_payload.get("data", {})
        start_time = changes.get("startTime")
        end_time = changes.get("endTime")
        if start_time or end_time:
            self._request(
                "POST",
                f"/api/admin/bookings/{booking_id}/reschedule",
                admin=True,
                json={
                    "new_start": start_time or current["start_time"],
                    "new_end": end_time or current["end_time"],
                },
            )
        if "notes" in changes:
            self._request(
                "PUT",
                f"/api/admin/bookings/{booking_id}",
                admin=True,
                json={"notes": changes.get("notes")},
            )
        status = changes.get("status")
        action = {
            "scheduled": "confirm",
            "completed": "complete",
            "no_show": "noshow",
            "cancelled": "cancel",
        }.get(status)
        if action:
            try:
                self._request(
                    "POST",
                    f"/api/admin/bookings/{booking_id}/{action}",
                    admin=True,
                )
            except BookingApiError as exc:
                if not (status == "scheduled" and exc.status_code == 400):
                    raise
        refreshed = self._request(
            "GET", f"/api/admin/bookings/{booking_id}", admin=True
        ).get("data", current)
        return self._map_booking(refreshed)

    def cancel_booking(self, booking_id: str | int) -> None:
        self._request(
            "POST", f"/api/admin/bookings/{booking_id}/cancel", admin=True
        )

    @staticmethod
    def _map_booking(booking: dict[str, Any]) -> dict[str, Any]:
        client = booking.get("client") or {}
        service = booking.get("service") or {}
        return {
            "id": str(booking["id"]),
            "customerPhone": client.get("phone") or "",
            "summary": " - ".join(
                value for value in (client.get("name"), service.get("name")) if value
            ) or "Booking",
            "startTime": booking.get("start_time"),
            "endTime": booking.get("end_time"),
            "status": _assistant_status(booking.get("status")),
            "notes": booking.get("notes") or "",
        }


def _optional_int(value: Any) -> Optional[int]:
    if value is None or str(value).strip() == "":
        return None
    return int(value)


def _as_datetime(value: str | datetime | None) -> datetime:
    if isinstance(value, datetime):
        return value
    if value is None:
        raise BookingApiError("A booking time is required.", status_code=422)
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def _error_message(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    error = payload.get("error")
    if isinstance(error, dict):
        return str(error.get("message") or error.get("code") or "")
    detail = payload.get("detail")
    return str(detail) if detail else ""


def _assistant_status(status: Any) -> str:
    normalized = str(status or "").lower()
    if normalized in {"pending", "confirmed", "rescheduled"}:
        return "scheduled"
    if normalized in {"no-show", "noshow"}:
        return "no_show"
    return normalized or "scheduled"


def _provider_schedule_score(provider: dict[str, Any]) -> int:
    schedule = provider.get("weekly_schedule") or {}
    if not isinstance(schedule, dict):
        return 0
    score = 0
    for day in schedule.values():
        if isinstance(day, dict) and day.get("is_working"):
            score += 1 + len(day.get("active_slots") or [])
    return score
