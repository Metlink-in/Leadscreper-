from fastapi import Depends, HTTPException, Request, status
from app.services.auth_service import decode_access_token
from app.services.db_service import db_service

async def get_current_user(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        print("[AUTH] No access_token cookie found in request")
        return None
    print(f"[AUTH] Found access_token cookie (length: {len(token)})")
    
    if token.startswith("Bearer "):
        token = token[7:]
        
    payload = decode_access_token(token)
    if not payload:
        return None
        
    email = payload.get("sub")
    if not email:
        return None
        
    user = await db_service.get_user_by_email(email)
    return user

async def require_user(user = Depends(get_current_user)):
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user
