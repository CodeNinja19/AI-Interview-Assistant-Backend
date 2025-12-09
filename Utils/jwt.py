import jwt
from dotenv import load_dotenv
import os
load_dotenv()
from datetime import datetime, timedelta, timezone

SECRET_KEY = os.getenv("JWT_SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")
TOKEN_EXPIRE_MINUTES = os.getenv("TOKEN_EXPIRE_MINUTES")

def create_jwt_token(username: str):
    expire = datetime.now(timezone.utc) + timedelta(minutes=int(TOKEN_EXPIRE_MINUTES))
    to_encode = {"sub": username, "exp": expire}
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def verify_jwt_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get("sub")
    except jwt.PyJWTError:
        return None

