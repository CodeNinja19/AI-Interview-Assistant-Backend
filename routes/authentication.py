from fastapi import APIRouter, Request, HTTPException, status, Response, Cookie
from mongodb.userdb import create_user, verify_user_password, get_user_by_username
from mongodb.schema.userSchema import UserCreate
from Utils.jwt import create_jwt_token, verify_jwt_token

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/register")
async def register(user: UserCreate, request: Request, response: Response):
    user_id = await create_user(request, user)
    token = create_jwt_token(user.username)
    response.set_cookie(key="access_token", value=token, httponly=True)
    return {"message": "User registered successfully", "user_id": user_id}

@router.post("/login")
async def login(user: UserCreate, request: Request, response: Response):
    is_valid = await verify_user_password(request, user.username, user.password)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password"
        )
    token = create_jwt_token(user.username)
    response.set_cookie(key="access_token", value=token, httponly=True)
    return {"message": "Login successful"}

@router.get("/status")
async def login_status(access_token: str = Cookie(None), request: Request = None):
    if not access_token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    username = verify_jwt_token(access_token)
    if not username:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    user = get_user_by_username(request ,username)
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    return {"message": "User is logged in", "username": username}