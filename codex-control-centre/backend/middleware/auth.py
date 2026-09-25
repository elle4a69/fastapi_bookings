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
        
    if not token or token != settings.token_secret:
        raise HTTPException(status_code=401, detail="Authentication required")
        
    return token
