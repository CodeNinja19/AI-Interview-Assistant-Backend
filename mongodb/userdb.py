import bcrypt
from fastapi import Request, HTTPException
from mongodb.schema.userSchema import UserCreate, UserInDB

async def create_user(request: Request, user: UserCreate) -> str:
    """
    Create a new user with a hashed password and store in the 'users' collection.
    """
    # Check if username already exists
    existing = await request.app.database["users"].find_one({"username": user.username})
    if existing:
        raise HTTPException(status_code=400, detail="Username already exists")

    hashed_password = bcrypt.hashpw(user.password.encode('utf-8'), bcrypt.gensalt())
    user_doc = {
        "username": user.username,
        "password_hash": hashed_password.decode('utf-8')
    }
    result = await request.app.database["users"].insert_one(user_doc)
    return str(result.inserted_id)

async def get_user_by_username(request: Request, username: str) -> UserInDB | None:
    """
    Retrieve a user document by username.
    """
    user_doc = await request.app.database["users"].find_one({"username": username})
    if user_doc:
        return UserInDB(
            id=str(user_doc["_id"]),
            username=user_doc["username"],
            password_hash=user_doc["password_hash"]
        )
    return None

async def verify_user_password(request: Request, username: str, password: str) -> bool:
    """
    Verify a user's password.
    """
    user = await get_user_by_username(request, username)
    if not user:
        return False
    return bcrypt.checkpw(password.encode('utf-8'), user.password_hash.encode('utf-8'))