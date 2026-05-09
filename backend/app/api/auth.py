from fastapi import APIRouter, HTTPException, status
from app.models.schemas import LoginRequest, TokenResponse
from app.core.auth import authenticate_user, create_token

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest):
    user = authenticate_user(req.username, req.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="아이디 또는 비밀번호 오류")
    token = create_token(user.user_id, user.department, user.is_admin)
    return TokenResponse(access_token=token)
