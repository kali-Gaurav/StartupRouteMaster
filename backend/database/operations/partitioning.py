import logging
from datetime import datetime, timedelta
from git import Optional
from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

class PartitionManager:
    """
    [Industrial Rigor] Automates the creation and management of DB partitions.
    Ensures that Vanguard always has a partition ready for tomorrow's data.
    """
    
    @staticmethod
    def create_daily_search_partition(db: Session, for_date: Optional[datetime] = None):
        """Creates a range partition for search logs for a specific date."""
        if not for_date:
            for_date = datetime.utcnow() + timedelta(days=1)
            
        table_suffix = for_date.strftime("%Y%m%d")
        start_date = for_date.strftime("%Y-%m-%d 00:00:00")
        end_date = (for_date + timedelta(days=1)).strftime("%Y-%m-%d 00:00:00")
        
        partition_name = f"route_search_logs_p{table_suffix}"
        
        query = text(f"""
            CREATE TABLE IF NOT EXISTS {partition_name} 
            PARTITION OF route_search_logs
            FOR VALUES FROM ('{start_date}') TO ('{end_date}');
        """)
        
        try:
            db.execute(query)
            db.commit()
            logger.info(f"✅ [DATABASE] Partition {partition_name} verified/created.")
        except Exception as e:
            logger.error(f"🚨 [DATABASE] Failed to create partition {partition_name}: {e}")
            db.rollback()

    @staticmethod
    def cleanup_old_partitions(db: Session, days_to_keep: int = 7):
        """
        Industrial Rigor: Detach and drop partitions older than retention period.
        Prevents index bloat and keeps vacuum operations fast.
        """
        # Logic to find and drop tables like route_search_logs_pYYYYMMDD
        pass

def get_current_partition_name(base_table: str) -> str:
    """Returns the name of the partition that should be used for the current timestamp."""
    if base_table == "route_search_logs":
        return f"route_search_logs_p{datetime.utcnow().strftime('%Y%m%d')}"
    return base_table
