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

@auth_router.post("/signup")
def signup(email: str = Form(...), password: str = Form(...), company_name: str = Form(...), db: Session = Depends(get_db)):
    """Public endpoint to create a new merchant and tenant admin."""
    from models import Merchant, User, TenantConfig
    from auth import hash_password
    import secrets

    # Check if merchant exists (simple check, normally more robust)
    existing_merchant = db.query(Merchant).execution_options(skip_tenant_check=True).filter(Merchant.name == company_name).first()
    if existing_merchant:
        raise HTTPException(status_code=400, detail="Company name already registered")
        
    existing_user = db.query(User).execution_options(skip_tenant_check=True).filter(User.email == email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    # 1. Create Merchant
    new_merchant = Merchant(
        name=company_name,
        api_key=secrets.token_hex(32),
        is_active=True
    )
    db.add(new_merchant)
    db.flush() # flush to get the ID

    # 2. Create User
    new_user = User(
        tenant_id=new_merchant.id,
        email=email,
        hashed_password=hash_password(password),
        role="TENANT_ADMIN",
        is_active=True
    )
    db.add(new_user)
    
    # 3. Create Default TenantConfig
    config = TenantConfig(
        tenant_id=new_merchant.id,
        pii_fields=["email", "full_name", "phone"],
        data_residency_region="US",
        churn_threshold=0.75
    )
    db.add(config)
    
    tenant_id = new_merchant.id
    db.commit()
    
    return {"message": "Account created successfully", "tenant_id": tenant_id}

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
