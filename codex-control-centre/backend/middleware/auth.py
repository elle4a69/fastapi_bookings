"""Authentication boundary for standalone and mounted Control Centre routes."""

from fastapi import HTTPException, Request

from backend.config import settings


def _header_token(request: Request) -> str | None:
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header.removeprefix("Bearer ").strip() or None
    return request.headers.get("X-Token")


def _is_fastapi_bookings_mount(request: Request) -> bool:
    """Return true only for the native FastAPI Bookings application object."""
    try:
        from app.main import app as fastapi_bookings_app

        return request.app is fastapi_bookings_app
    except Exception:
        return False


async def _verify_mounted_platform_owner(request: Request, token: str | None):
    """Resolve the native tenant/user identity and require platform-owner scope."""
    if not token:
        raise HTTPException(status_code=401, detail="Authentication required")

    from app.api.deps import get_current_tenant, get_current_user, require_platform_owner
    from app.db.database import SessionLocal, get_db as app_get_db

    overridden_get_db = request.app.dependency_overrides.get(app_get_db)
    if overridden_get_db:
        db_gen = overridden_get_db()
        db = next(db_gen)
        should_close = False
    else:
        db = SessionLocal()
        should_close = True

    try:
        try:
            tenant = await get_current_tenant(request=request, db=db)
            user = await get_current_user(x_token=token, tenant=tenant, db=db)
            return await require_platform_owner(current_user=user)
        except HTTPException as exc:
            if exc.status_code == 403:
                raise
            raise HTTPException(status_code=401, detail="Authentication required") from exc
    finally:
        if should_close:
            db.close()


async def _verify_local_development_bypass(request: Request, token: str):
    """Retained compatibility helper, constrained to the native owner boundary."""
    if token != "local-development-bypass" or not _is_fastapi_bookings_mount(request):
        raise HTTPException(status_code=401, detail="Authentication required")

    from app.core.config import settings as app_settings

    if not app_settings.LOCAL_AUTH_BYPASS:
        raise HTTPException(status_code=401, detail="Authentication required")
    return await _verify_mounted_platform_owner(request, token)


async def verify_auth(request: Request):
    """Authenticate a protected Control Centre HTTP operation.

    The embedded application delegates exclusively to FastAPI Bookings identity
    and platform-owner authorization. Its routes never accept the standalone
    shared secret, including the repository default ``local_secret``, and never
    accept bearer credentials in the query string.
    """
    token = _header_token(request)

    if _is_fastapi_bookings_mount(request):
        return await _verify_mounted_platform_owner(request, token)

    # Standalone compatibility. Query credentials remain limited to the
    # standalone server; embedded streams use one-use SSE tickets instead.
    if not token:
        token = request.query_params.get("token")
    if token and token == settings.token_secret:
        return token

    raise HTTPException(status_code=401, detail="Authentication required")
