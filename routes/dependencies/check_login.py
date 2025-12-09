from fastapi import Depends, HTTPException, Request
from Utils.jwt import verify_jwt_token
from mongodb.userdb import get_user_by_username

async def check_login(request: Request):
    access_token = request.cookies.get("access_token")
    if not access_token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    username = verify_jwt_token(access_token)
    if not username:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user = await get_user_by_username(request, username)
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    request.state.user = user  # Attach user info to request.state
    return user
