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
            from app.db.database import SessionLocal
            from app.models.user import User
            payload = decode_access_token(token)
            if payload and payload.get("sub"):
                with SessionLocal() as db:
                    user = db.query(User).filter(User.id == int(payload["sub"])).first()
                    if user and user.role in ("owner", "admin", "manager", "superadmin"):
                        return user
        except Exception:
            pass

    raise HTTPException(status_code=401, detail="Authentication required")
