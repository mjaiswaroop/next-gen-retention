"""
auth.py — JWT Authentication + RBAC
======================================
Implements Section 5: Role-Based Access Control.
Roles: SUPER_ADMIN | TENANT_ADMIN | ANALYST | CAMPAIGN_MANAGER | PII_VIEWER

Changes from original:
- JWT payload now includes role + user_id (in addition to merchant/tenant sub)
- Added create_user_token() for email+password login
- Added require_role() FastAPI dependency factory
- Added verify_api_key() for scoped machine-to-machine auth
- Passlib bcrypt for password hashing
"""

import hashlib
import os
from datetime import datetime, timedelta, timezone
from functools import wraps
from typing import Optional

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer, APIKeyHeader
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from config import settings
from database import get_db, active_tenant_id
from models import ApiKey, Merchant, User

security = HTTPBearer()
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

VALID_ROLES = {"SUPER_ADMIN", "TENANT_ADMIN", "ANALYST", "CAMPAIGN_MANAGER", "PII_VIEWER"}


# ─────────────────────────────────────────────────────────────────────────────
# Password Utilities
# ─────────────────────────────────────────────────────────────────────────────

import bcrypt

def hash_password(plain_password: str) -> str:
    """Returns bcrypt hash of the given password."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(plain_password.encode('utf-8'), salt).decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plaintext password against stored bcrypt hash."""
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))


# ─────────────────────────────────────────────────────────────────────────────
# Token Creation
# ─────────────────────────────────────────────────────────────────────────────

def create_access_token(merchant_id: int) -> str:
    """Creates a merchant-scoped JWT (backwards-compatible with existing endpoints)."""
    payload = {
        "sub":         str(merchant_id),
        "tenant_id":   merchant_id,
        "role":        "TENANT_ADMIN",
        "user_id":     None,
        "token_type":  "merchant",
        "exp":         datetime.now(timezone.utc) + timedelta(
                           minutes=settings.access_token_expire_minutes),
        "iat":         datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def create_user_token(user_id: str, tenant_id: int, role: str) -> str:
    """
    Creates a user-scoped JWT with role embedded.
    Used for the dashboard email+password login flow (Section 10).
    """
    if role not in VALID_ROLES:
        raise ValueError(f"Invalid role: {role}. Must be one of {VALID_ROLES}")

    payload = {
        "sub":        str(user_id),
        "tenant_id":  tenant_id,
        "role":       role,
        "user_id":    user_id,
        "token_type": "user",
        "exp":        datetime.now(timezone.utc) + timedelta(
                          minutes=settings.access_token_expire_minutes),
        "iat":        datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


# ─────────────────────────────────────────────────────────────────────────────
# Auth Dependencies
# ─────────────────────────────────────────────────────────────────────────────

def get_current_merchant(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> Merchant:
    """
    FastAPI dependency: validates JWT and returns the Merchant object.
    Raises 401 on invalid/expired token. Raises 403 if account is inactive.
    Backwards-compatible with existing routes.
    """
    exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            credentials.credentials, settings.secret_key, algorithms=["HS256"]
        )
        merchant_id = int(payload.get("tenant_id") or payload["sub"])
    except (JWTError, ValueError, KeyError):
        raise exc

    merchant = db.query(Merchant).execution_options(skip_tenant_check=True).filter(Merchant.id == merchant_id).first()
    if not merchant:
        raise exc
    if not merchant.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Merchant account is inactive",
        )
        
    active_tenant_id.set(merchant.id)
    return merchant


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> dict:
    """
    FastAPI dependency: validates JWT and returns a context dict with
    user_id, tenant_id, role fields.
    Accepts both merchant tokens and user tokens.
    """
    exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            credentials.credentials, settings.secret_key, algorithms=["HS256"]
        )
    except JWTError:
        raise exc

    tenant_id = payload.get("tenant_id")
    role = payload.get("role", "ANALYST")
    user_id = payload.get("user_id")

    if not tenant_id:
        raise exc

    # Verify tenant is still active
    merchant = db.query(Merchant).execution_options(skip_tenant_check=True).filter(Merchant.id == tenant_id).first()
    if not merchant or not merchant.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant account is inactive",
        )

    active_tenant_id.set(tenant_id)
    return {
        "user_id":   user_id,
        "tenant_id": tenant_id,
        "role":      role,
        "merchant":  merchant,
    }


def require_role(*allowed_roles: str):
    """
    FastAPI dependency factory for role-based access control.
    Usage:
        @router.get("/admin", dependencies=[Depends(require_role("SUPER_ADMIN", "TENANT_ADMIN"))])

    Raises 403 if current user's role is not in allowed_roles.
    """
    def _dependency(current_user: dict = Depends(get_current_user)) -> dict:
        role = current_user.get("role")
        if role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{role}' is not authorized. Required: {list(allowed_roles)}",
            )
        return current_user
    return _dependency


def authenticate_user(email: str, password: str, tenant_id: int, db: Session) -> Optional[User]:
    """
    Verifies email + password for a user in a given tenant.
    Returns User object on success, None on failure.
    """
    user = (
        db.query(User)
        .execution_options(skip_tenant_check=True) # since we haven't authenticated yet
        .filter(User.tenant_id == tenant_id, User.email == email, User.is_active == True)
        .first()
    )
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


# ─────────────────────────────────────────────────────────────────────────────
# API Key Authentication
# ─────────────────────────────────────────────────────────────────────────────

def verify_api_key(
    api_key_value: Optional[str] = Security(api_key_header),
    db: Session = Depends(get_db),
) -> Optional[dict]:
    """
    FastAPI dependency: validates X-API-Key header.
    Returns context dict if valid, raises 401 if invalid.
    Gracefully returns None if no key provided (allows fallback to JWT).
    """
    if not api_key_value:
        return None

    key_hash = hashlib.sha256(api_key_value.encode()).hexdigest()
    api_key = (
        db.query(ApiKey)
        .execution_options(skip_tenant_check=True)
        .filter(
            ApiKey.key_hash == key_hash,
            ApiKey.is_revoked == False,
        )
        .first()
    )
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked API key",
        )

    # Check expiry
    if api_key.expires_at and api_key.expires_at < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key has expired",
        )

    # Update last_used_at (non-blocking)
    try:
        active_tenant_id.set(api_key.tenant_id)
        api_key.last_used_at = datetime.now(timezone.utc)
        db.commit()
    except Exception:
        db.rollback()

    return {
        "key_id":    api_key.key_id,
        "tenant_id": api_key.tenant_id,
        "scopes":    api_key.scopes or [],
        "role":      "API_KEY",
    }


def require_scope(scope: str):
    """
    FastAPI dependency factory for API key scope enforcement.
    Usage:
        @router.post("/ingest", dependencies=[Depends(require_scope("data_ingest"))])
    """
    def _dependency(api_key_ctx: dict = Depends(verify_api_key)) -> dict:
        if not api_key_ctx:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="API key required for this endpoint",
            )
        if scope not in (api_key_ctx.get("scopes") or []):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"API key does not have scope: {scope}",
            )
        return api_key_ctx
    return _dependency
