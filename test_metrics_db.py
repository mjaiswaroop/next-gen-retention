import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))
from database import SessionLocal, active_tenant_id
from models import ModelRegistry

db = SessionLocal()
tenant_id = 1
active_tenant_id.set(tenant_id)
print("Querying ModelRegistry...")
try:
    latest_model = db.query(ModelRegistry).filter(ModelRegistry.tenant_id == tenant_id, ModelRegistry.is_active == True).order_by(ModelRegistry.created_at.desc()).first()
    print("Success:", latest_model)
except Exception as e:
    import traceback
    traceback.print_exc()
