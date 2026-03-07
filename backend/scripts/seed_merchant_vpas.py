from database.session import SessionLocal
from database.models import MerchantVPA
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def seed_merchant_vpas():
    db = SessionLocal()
    try:
        # Ensure table exists
        from database.models import MerchantVPA
        MerchantVPA.__table__.create(bind=db.get_bind(), checkfirst=True)
        
        vpas = [
            {"vpa": "anthonynagar1122-1@oksbi", "name": "RouteMaster Main", "daily_limit": 100000.0},
            {"vpa": "8529841981@ptsbi", "name": "RouteMaster Secondary", "daily_limit": 100000.0},
            {"vpa": "gauravnagar@okaxis", "name": "RouteMaster Backup", "daily_limit": 50000.0},
        ]
        
        for vpa_data in vpas:
            existing = db.query(MerchantVPA).filter(MerchantVPA.vpa == vpa_data["vpa"]).first()
            if not existing:
                new_vpa = MerchantVPA(**vpa_data)
                db.add(new_vpa)
                logger.info(f"Added VPA: {vpa_data['vpa']}")
            else:
                logger.info(f"VPA already exists: {vpa_data['vpa']}")
        
        db.commit()
        logger.info("Merchant VPAs seeded successfully.")
    except Exception as e:
        logger.error(f"Error seeding Merchant VPAs: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed_merchant_vpas()
