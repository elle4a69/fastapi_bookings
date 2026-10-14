from fastapi import HTTPException, Request
from backend.config import settings

async def verify_auth(request: Request):
    token = None
    
    # Check Authorization header
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
    
    # Check query param (for EventSource/SSE streams)
    if not token:
        token = request.query_params.get("token")

    # Check X-Token header
    if not token:
        token = request.headers.get("X-Token")

    if token and token == settings.token_secret:
        return token

    # Check if running within FastAPI Bookings with decoded admin user
    if token:
        try:
            from app.core.security import decode_access_token
            from app.models.user import User
            payload = decode_access_token(token)
            if payload and payload.get("sub"):
                from app.db.database import get_db as app_get_db
                overridden_get_db = request.app.dependency_overrides.get(app_get_db)
                if overridden_get_db:
                    db_gen = overridden_get_db()
                    db = next(db_gen)
                    should_close = False
                else:
                    from app.db.database import SessionLocal
                    db = SessionLocal()
                    should_close = True

                try:
                    tenant_header = request.headers.get("X-Tenant")
                    tenant = None
                    if tenant_header:
                        from app.models.tenant import Tenant
                        tenant = db.query(Tenant).filter(Tenant.subdomain == tenant_header).first()

                    user_query = db.query(User).filter(User.id == int(payload["sub"]))
                    if tenant:
                        user_query = user_query.filter(User.tenant_id == tenant.id)
                    user = user_query.first()

                    if user:
                        if user.role in ("owner", "admin", "manager", "superadmin"):
                            return user
                        raise HTTPException(status_code=403, detail="Admin access required")
                finally:
                    if should_close:
                        db.close()
        except HTTPException:
            raise
        except Exception:
            pass

    raise HTTPException(status_code=401, detail="Authentication required")
