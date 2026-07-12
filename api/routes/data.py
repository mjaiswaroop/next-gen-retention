"""
api/routes/data.py
"""
import pandas as pd
from io import BytesIO
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel

from database import get_db
from auth import get_current_user
from models import Customer, TenantConfig, TenantIntegration
from schemas.tenant_feature import TenantSchemaRegistry, FeatureDefinition, FeatureType
from pydantic import ValidationError

data_router = APIRouter()
router = data_router

class DBCredentials(BaseModel):
    db_type: str  # e.g., 'postgresql'
    host: str
    port: str
    user: str
    password: str
    db_name: str
    table_name: str

def process_and_insert_dataframe(df: pd.DataFrame, tenant_id: int, db: Session) -> dict:
    config = db.query(TenantConfig).filter(TenantConfig.tenant_id == tenant_id).first()
    if not config:
        raise HTTPException(status_code=500, detail="Tenant configuration missing.")
        
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
    
    schema_registry = TenantSchemaRegistry(**config.feature_schema)
    DynamicValidator = schema_registry.build_dynamic_validator()
    records = df.to_dict(orient="records")
    
    validated_records = []
    for i, row in enumerate(records):
        try:
            valid_row = DynamicValidator(**row).model_dump()
            validated_records.append(valid_row)
        except ValidationError as e:
            raise HTTPException(status_code=422, detail=f"Schema validation failed at row {i}: {e}")
            
    core_columns = {'user_id', 'recency_days', 'frequency', 'monetary_value', 'session_failures', 'payment_friction_index', 'active_support_tickets', 'segment'}
    customers = []
    
    def safe_int(val):
        try: return int(float(val))
        except (ValueError, TypeError): return 0
    def safe_float(val):
        try: return float(val)
        except (ValueError, TypeError): return 0.0

    for row in validated_records:
        extra_features = {k: v for k, v in row.items() if k not in core_columns}
        
        # Flexibly handle user_id vs customer_id
        extracted_user_id = row.get('user_id') or row.get('customer_id')
        if not extracted_user_id:
            import uuid
            extracted_user_id = f"UNKNOWN_{uuid.uuid4().hex[:8]}"

        customer = Customer(
            merchant_id=tenant_id,
            user_id=str(extracted_user_id),
            recency_days=safe_float(row.get('recency_days', 0.0)),
            frequency=safe_int(row.get('frequency', 0)),
            monetary_value=safe_float(row.get('monetary_value', 0.0)),
            session_failures=safe_int(row.get('session_failures', 0)),
            payment_friction_index=safe_float(row.get('payment_friction_index', 0.0)),
            active_support_tickets=safe_int(row.get('active_support_tickets', 0)),
            segment=str(row.get('segment', 'New')),
            extra_features=extra_features
        )
        customers.append(customer)
        
    try:
        user_ids = [c.user_id for c in customers]
        if user_ids:
            # Upsert logic: Delete existing to prevent UNIQUE constraint errors
            db.query(Customer).filter(
                Customer.merchant_id == tenant_id,
                Customer.user_id.in_(user_ids)
            ).delete(synchronize_session=False)
            
        db.bulk_save_objects(customers)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error during insertion: {e}")
        
    return {"message": f"Successfully validated and uploaded {len(customers)} records against strict tenant schema.", "count": len(customers)}

def bg_process_and_insert(df: pd.DataFrame, tenant_id: int):
    from database import SessionLocal, active_tenant_id
    active_tenant_id.set(tenant_id)
    db = SessionLocal()
    try:
        process_and_insert_dataframe(df, tenant_id, db)
    except Exception as e:
        print(f"Background processing failed: {e}")
    finally:
        db.close()

@data_router.post("/upload_csv")
async def upload_csv(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Only CSV files are supported")
        
    try:
        contents = await file.read()
        df = pd.read_csv(BytesIO(contents))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read CSV: {e}")
        
    background_tasks.add_task(bg_process_and_insert, df, current_user["tenant_id"])
    return {"message": "Upload received. Data is being processed in the background."}

@data_router.post("/integration/db")
def save_db_config(
    creds: DBCredentials,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    tenant_id = current_user["tenant_id"]
    integration = db.query(TenantIntegration).filter(
        TenantIntegration.tenant_id == tenant_id,
        TenantIntegration.integration_name == "external_db"
    ).first()
    
    config_data = creds.model_dump()
    
    if integration:
        integration.config = config_data
    else:
        integration = TenantIntegration(
            tenant_id=tenant_id,
            integration_name="external_db",
            is_enabled=True,
            config=config_data
        )
        db.add(integration)
        
    db.commit()
    return {"message": "Database credentials saved successfully."}

@data_router.post("/integration/db/sync")
def sync_db(
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    tenant_id = current_user["tenant_id"]
    integration = db.query(TenantIntegration).filter(
        TenantIntegration.tenant_id == tenant_id,
        TenantIntegration.integration_name == "external_db"
    ).first()
    
    if not integration or not integration.config:
        raise HTTPException(status_code=400, detail="No external database configured.")
        
    cfg = integration.config
    
    # Construct sqlalchemy URL
    from sqlalchemy import create_engine
    
    try:
        if cfg["db_type"] == "postgresql":
            url = f"postgresql://{cfg['user']}:{cfg['password']}@{cfg['host']}:{cfg['port']}/{cfg['db_name']}"
        elif cfg["db_type"] == "mysql":
            url = f"mysql+pymysql://{cfg['user']}:{cfg['password']}@{cfg['host']}:{cfg['port']}/{cfg['db_name']}"
        else:
            raise HTTPException(status_code=400, detail="Unsupported database type")
            
        engine = create_engine(url)
        df = pd.read_sql_table(cfg["table_name"], engine)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch data from database: {e}")
        
    background_tasks.add_task(bg_process_and_insert, df, tenant_id)
    return {"message": "Sync started. Data is being fetched and processed in the background."}
