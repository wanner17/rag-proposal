from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from app.core.config import settings
from app.models.schemas import UserInfo

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# 임시 사용자 DB — 실제 운영 시 DB로 교체
FAKE_USERS = {
    "admin": {"password": "admin1234", "department": "전체", "is_admin": True},
    "user1": {"password": "user1234", "department": "공공사업팀", "is_admin": False},
}


def create_token(user_id: str, department: str, is_admin: bool) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": user_id,
        "dept": department,
        "admin": is_admin,
        "exp": expire,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def authenticate_user(username: str, password: str) -> UserInfo | None:
    user = FAKE_USERS.get(username)
    if not user or user["password"] != password:
        return None
    return UserInfo(
        user_id=username,
        username=username,
        department=user["department"],
        is_admin=user["is_admin"],
    )


async def get_current_user(token: str = Depends(oauth2_scheme)) -> UserInfo:
    exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="인증 실패",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        user_id: str = payload.get("sub")
        if not user_id:
            raise exc
        return UserInfo(
            user_id=user_id,
            username=user_id,
            department=payload.get("dept", ""),
            is_admin=payload.get("admin", False),
        )
    except JWTError:
        raise exc
