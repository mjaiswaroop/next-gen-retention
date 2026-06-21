"""
api/routes/auth.py
"""
from fastapi import APIRouter, Depends, HTTPException, Form
from sqlalchemy.orm import Session
from typing import List

from database import get_db
from auth import get_current_user, require_role, authenticate_user, create_user_token

auth_router = APIRouter()
router = auth_router

@auth_router.post("/login")
def login(username: str = Form(...), password: str = Form(...), client_id: int = Form(...), db: Session = Depends(get_db)):
    """Issues user-scoped JWT for dashboard login."""
    user = authenticate_user(username, password, client_id, db)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_user_token(str(user.user_id), user.tenant_id, user.role)
    return {"access_token": token, "token_type": "bearer", "role": user.role}

@auth_router.post("/keys", dependencies=[Depends(require_role("SUPER_ADMIN", "TENANT_ADMIN"))])
def create_api_key(name: str, scopes: List[str], current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """Generates a scoped API key."""
    import secrets, hashlib
    from models import ApiKey
    raw_key = secrets.token_urlsafe(32)
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    
    new_key = ApiKey(
        tenant_id=current_user["tenant_id"],
        key_name=name,
        key_hash=key_hash,
        scopes=scopes,
    )
    db.add(new_key)
    db.commit()
    return {"message": "Key created", "api_key": raw_key}
