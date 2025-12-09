from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from Utils.jwt import verify_jwt_token
from mongodb.userdb import get_user_by_username

class CheckLoginMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        access_token = request.cookies.get("access_token")
        if not access_token:
            return JSONResponse(status_code=401, content={"detail": "Not authenticated"})
        username = verify_jwt_token(access_token)
        if not username:
            return JSONResponse(status_code=401, content={"detail": "Invalid or expired token"})
        user = await get_user_by_username(request, username)
        if user is None:
            return JSONResponse(status_code=401, content={"detail": "User not found"})
        # Optionally attach user info to request.state
        request.state.user = user
        response = await call_next(request)
        return response