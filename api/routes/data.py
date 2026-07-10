"""
api/routes/data.py
"""
import pandas as pd
from io import BytesIO
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from auth import get_current_user
from models import Customer

data_router = APIRouter()
router = data_router

@data_router.post("/upload_csv")
async def upload_csv(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Parses a CSV file, strictly validates it against the tenant's schema, and inserts."""
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Only CSV files are supported")
        
    try:
        contents = await file.read()
        df = pd.read_csv(BytesIO(contents))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read CSV: {e}")
        
    tenant_id = current_user["tenant_id"]
    
    # Query TenantConfig for existing schema
    from models import TenantConfig
    config = db.query(TenantConfig).filter(TenantConfig.tenant_id == tenant_id).first()
    if not config:
        raise HTTPException(status_code=500, detail="Tenant configuration missing.")
        
    from schemas.tenant_feature import TenantSchemaRegistry, FeatureDefinition, FeatureType
    from pydantic import ValidationError
    
    # Infer schema if none exists (Option A)
    if not config.feature_schema:
        core_cols = {'user_id', 'recency_days', 'frequency', 'monetary_value', 'session_failures', 'payment_friction_index', 'active_support_tickets', 'segment'}
        
        core_features = []
        custom_features = []
        
        for col in df.columns:
            dtype = FeatureType.CATEGORICAL
            if pd.api.types.is_numeric_dtype(df[col]):
                dtype = FeatureType.NUMERIC
            elif pd.api.types.is_bool_dtype(df[col]):
                dtype = FeatureType.BOOLEAN
                
            feat = FeatureDefinition(name=col, dtype=dtype, is_required=True if col == 'user_id' else False)
            if col in core_cols:
                core_features.append(feat.model_dump())
            else:
                custom_features.append(feat.model_dump())
                
        schema_dict = {
            "tenant_id": tenant_id,
            "core_features": core_features,
            "custom_features": custom_features
        }
        config.feature_schema = schema_dict
        db.commit()
    
    # Re-read schema after potential creation
    schema_registry = TenantSchemaRegistry(**config.feature_schema)
    DynamicValidator = schema_registry.build_dynamic_validator()
    
    records = df.to_dict(orient="records")
    
    # Enforce Pydantic Validation
    validated_records = []
    for i, row in enumerate(records):
        try:
            # Pydantic strictly checks types and constraints
            valid_row = DynamicValidator(**row).model_dump()
            validated_records.append(valid_row)
        except ValidationError as e:
            raise HTTPException(status_code=422, detail=f"Schema validation failed at row {i}: {e}")
            
    # If we made it here, the data contract is fully respected.
    core_columns = {'user_id', 'recency_days', 'frequency', 'monetary_value', 'session_failures', 'payment_friction_index', 'active_support_tickets', 'segment'}
    customers = []
    
    for row in validated_records:
        extra_features = {k: v for k, v in row.items() if k not in core_columns}
        
        customer = Customer(
            merchant_id=tenant_id,
            user_id=str(row.get('user_id', f"UNKNOWN_{len(customers)}")),
            recency_days=float(row.get('recency_days', 0.0)),
            frequency=int(row.get('frequency', 0)),
            monetary_value=float(row.get('monetary_value', 0.0)),
            session_failures=int(row.get('session_failures', 0)),
            payment_friction_index=float(row.get('payment_friction_index', 0.0)),
            active_support_tickets=int(row.get('active_support_tickets', 0)),
            segment=str(row.get('segment', 'New')),
            extra_features=extra_features
        )
        customers.append(customer)
        
    try:
        db.bulk_save_objects(customers)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error during insertion: {e}")
        
    return {"message": f"Successfully validated and uploaded {len(customers)} records against strict tenant schema.", "count": len(customers)}
