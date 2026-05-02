from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from datetime import datetime, timezone

from app.auth import get_current_user, get_password_hash, verify_password, create_access_token, create_service_token
from app.database import get_db
from app.models import User, RevokedToken
from app.schemas import UserRead, UserUpdate, TokenResponse
import jwt
import os

users_router = APIRouter(prefix="/users", tags=["users"])
auth_router = APIRouter(prefix="/auth", tags=["auth"])


@users_router.get("/me", response_model=UserRead)
async def get_current_user_profile(current_user: User = Depends(get_current_user)):
    return UserRead.from_orm(current_user)


@users_router.put("/me", response_model=UserRead)
async def update_current_user_profile(
    data: UserUpdate,
    current_user: User = Depends(get_current_user),
    db = Depends(get_db)
):
    if data.display_name is not None:
        current_user.display_name = data.display_name
    if data.password is not None:
        current_user.hashed_password = get_password_hash(data.password)
    await db.commit()
    return UserRead.from_orm(current_user)


@users_router.get("", response_model=list[UserRead])
async def list_users(current_user: User = Depends(get_current_user), db = Depends(get_db)):
    result = await db.execute(select(User))
    users = result.scalars().all()
    return [UserRead.from_orm(u) for u in users]


@auth_router.post("/token", response_model=TokenResponse)
async def login(
    request: Request,
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db = Depends(get_db)
):
    result = await db.execute(select(User).where(User.username == form_data.username))
    user = result.scalar_one_or_none()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    
    token = create_access_token(user.id, user.username, expiry_days=1)
    response.set_cookie(
        key="token",
        value=token,
        httponly=True,
        samesite="strict",
        max_age=86400,
        path="/"
    )
    return TokenResponse(access_token=token)


@auth_router.post("/revoke", status_code=204)
async def revoke_token(
    request: Request,
    current_user: User = Depends(get_current_user),
    db = Depends(get_db)
):
    token = request.cookies.get("token")
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    jwt_secret = os.environ["JWT_SECRET"]
    try:
        payload = jwt.decode(token, jwt_secret, algorithms=["HS256"])
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    jti = payload.get("jti")
    exp = payload.get("exp")
    if not jti or not exp:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    expires_at = datetime.fromtimestamp(exp, tz=timezone.utc)
    revoked_token = RevokedToken(jti=jti, expires_at=expires_at, revoked_by=current_user.id)
    db.add(revoked_token)
    await db.commit()</content>
<parameter name="filePath">app/routers/users.py