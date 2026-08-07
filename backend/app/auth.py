import uuid
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from secrets import token_urlsafe
from typing import Any

from fastapi import Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database import get_db
from app.models.user import RefreshToken, User
from app.models.revoked_token import RevokedToken

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token", auto_error=False)
TOKEN_AUDIENCE = "pollisync-api"
TOKEN_ISSUER = "pollisync"

ACCESS_TOKEN_COOKIE = "access_token"
REFRESH_TOKEN_COOKIE = "refresh_token"


def set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    secure = settings.is_production
    samesite = "none" if settings.is_production else "lax"
    response.set_cookie(
        key=ACCESS_TOKEN_COOKIE,
        value=access_token,
        httponly=True,
        secure=secure,
        samesite=samesite,
        max_age=settings.access_token_minutes * 60,
        path="/",
    )
    response.set_cookie(
        key=REFRESH_TOKEN_COOKIE,
        value=refresh_token,
        httponly=True,
        secure=secure,
        samesite=samesite,
        max_age=settings.refresh_token_days * 86400,
        path="/api/auth",
    )
    # Set XSRF-TOKEN cookie for double-submit cookie CSRF protection
    response.set_cookie(
        key="XSRF-TOKEN",
        value=token_urlsafe(32),
        httponly=False,
        secure=secure,
        samesite=samesite,
        max_age=settings.access_token_minutes * 60,
        path="/",
    )


def clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(key=ACCESS_TOKEN_COOKIE, path="/")
    response.delete_cookie(key=REFRESH_TOKEN_COOKIE, path="/api/auth")
    response.delete_cookie(key="XSRF-TOKEN", path="/")


def _get_cookie_token(request: Request) -> str | None:
    return request.cookies.get(ACCESS_TOKEN_COOKIE)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(user: User) -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.access_token_minutes)
    jti = str(uuid.uuid4())
    to_encode = {
        "sub": str(user.id),
        "email": user.email,
        "typ": "access",
        "iss": TOKEN_ISSUER,
        "aud": TOKEN_AUDIENCE,
        "iat": now,
        "exp": expire,
        "jti": jti,
    }
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)


def hash_refresh_token(token: str) -> str:
    return sha256(token.encode("utf-8")).hexdigest()


def create_refresh_token(user: User, db: Session) -> str:
    raw_token = token_urlsafe(48)
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_days)
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hash_refresh_token(raw_token),
            expires_at=expires_at,
        )
    )
    db.commit()
    return raw_token


def revoke_refresh_token(raw_token: str, db: Session) -> None:
    stored_token = db.query(RefreshToken).filter_by(token_hash=hash_refresh_token(raw_token)).one_or_none()
    if stored_token and stored_token.revoked_at is None:
        stored_token.revoked_at = datetime.now(timezone.utc)
        db.commit()


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.algorithm],
            audience=TOKEN_AUDIENCE,
            issuer=TOKEN_ISSUER,
        )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if payload.get("typ") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload


def _as_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def rotate_refresh_token(raw_token: str, db: Session) -> tuple[User, str]:
    stored_token = db.query(RefreshToken).filter_by(token_hash=hash_refresh_token(raw_token)).one_or_none()
    if not stored_token or stored_token.revoked_at is not None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )
    if _as_aware_utc(stored_token.expires_at) <= datetime.now(timezone.utc):
        stored_token.revoked_at = datetime.now(timezone.utc)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token expired",
        )
    user = db.get(User, stored_token.user_id)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    stored_token.revoked_at = datetime.now(timezone.utc)
    new_refresh_token = create_refresh_token(user, db)
    return user, new_refresh_token


def get_current_user(
    request: Request,
    token: str | None = Depends(oauth2_scheme),
    cookie_token: str | None = Depends(_get_cookie_token),
    db: Session = Depends(get_db),
) -> User:
    token_value = token or cookie_token
    if not token_value:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # Double-submit cookie CSRF check.
    # A request carrying an Origin header that is in allowed_origins is trusted
    # (browsers set Origin and scripts cannot forge it), so the XSRF header is
    # not required. This is what makes cookie auth work across the separate
    # frontend/backend origins in production. Requests without an Origin or from
    # a disallowed origin still require the double-submit XSRF header.
    if not token and cookie_token and request.method in {"POST", "PUT", "DELETE", "PATCH"}:
        origin = request.headers.get("origin", "").strip().rstrip("/")
        origin_trusted = bool(origin and origin in settings.allowed_origins)
        if not origin_trusted:
            csrf_cookie = request.cookies.get("XSRF-TOKEN")
            csrf_header = request.headers.get("X-XSRF-TOKEN") or request.headers.get("x-xsrf-token")
            if not csrf_cookie or not csrf_header or csrf_cookie != csrf_header:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="CSRF token validation failed",
                )
            
    payload = decode_access_token(token_value)
    
    # Check blacklist for access token revocation
    jti = payload.get("jti")
    if jti:
        is_revoked = db.scalar(
            select(RevokedToken).where(RevokedToken.jti == jti)
        )
        if is_revoked:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has been revoked",
                headers={"WWW-Authenticate": "Bearer"},
            )
            
    subject = payload.get("sub")
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = db.get(User, subject)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user
