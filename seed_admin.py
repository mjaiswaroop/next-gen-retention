import logging
from database import SessionLocal, engine, Base
from models import Merchant, User
from auth import hash_password
import secrets

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("retention_core.seed")

def seed():
    # Automatically create tables if they do not exist
    logger.info("Initializing database schemas...")
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    try:
        admin_exists = db.query(User).execution_options(skip_tenant_check=True).filter(User.email == "admin@retentioncore.com").first()
        if not admin_exists:
            logger.info("Auto-seeding default admin account...")
            m = db.query(Merchant).filter(Merchant.name == 'Retention Core Corp').first()
            if not m:
                m = Merchant(name='Retention Core Corp', api_key=secrets.token_urlsafe(32), is_active=True)
                db.add(m)
                db.commit()
            
            u = User(tenant_id=m.id, email='admin@retentioncore.com', hashed_password=hash_password('admin123'), role='SUPER_ADMIN', is_active=True)
            db.add(u)
            db.commit()
            logger.info("Admin account created successfully.")
        else:
            logger.info("Admin account already exists.")
    except Exception as e:
        logger.error(f"Failed to auto-seed database: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    seed()
