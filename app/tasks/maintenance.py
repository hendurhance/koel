from app.utils.custom_logger import get_logger
from datetime import datetime
from sqlalchemy import text
from app.db.database import get_db
from app.tasks.celery_app import celery_app
from app.utils.cache_manager import CacheManager

logger = get_logger(__name__)

@celery_app.task
def cleanup_old_task_records():
    """Cleanup old task records and perform database maintenance"""
    logger.info("Starting database maintenance task")

    # Get a database session
    db = next(get_db())

    try:
        # Clear Redis cache for job, retry, currencies, and exchange rates
        CacheManager.delete("job:*")
        CacheManager.delete("retry:*")
        CacheManager.delete("currencies:*")
        CacheManager.delete("currency:*")
        CacheManager.delete("exchange_rates:*")

        # Get current active partitions
        partitions_query = text("""
            SELECT tablename 
            FROM pg_tables 
            WHERE tablename LIKE 'exchange_rates_%'
            ORDER BY tablename;
        """)
        
        partitions = [row[0] for row in db.execute(partitions_query).fetchall()]
        logger.info(f"Found {len(partitions)} exchange rate partitions")
        
        # Run VACUUM on the main exchange_rates table
        db.execute(text("VACUUM ANALYZE exchange_rates"))
        
        # Run maintenance on each active partition
        retention_months = 6  # Keep 6 months of data
        today = datetime.now()
        
        for partition in partitions:
            try:
                # Extract year and month from partition name (exchange_rates_YYYY_MM)
                if '_' not in partition or len(partition.split('_')) < 3:
                    logger.warning(f"Skipping partition with invalid name format: {partition}")
                    continue
                    
                year_month = partition.split('_', 2)[2]  # Gets "YYYY_MM"
                if '_' not in year_month:
                    logger.warning(f"Skipping partition with invalid year_month format: {partition}")
                    continue
                    
                year, month = year_month.split('_')
                partition_date = datetime(int(year), int(month), 1)
                
                # Check if partition is within retention period
                if (today - partition_date).days > retention_months * 30:
                    logger.info(f"Dropping old partition: {partition}")
                    db.execute(text(f"DROP TABLE {partition}"))
                else:
                    # Optimize current partitions
                    logger.info(f"Running maintenance on partition: {partition}")
                    db.execute(text(f"VACUUM ANALYZE {partition}"))
            except Exception as e:
                logger.error(f"Error processing partition {partition}: {e}")

        # Run vacuum on currencies table
        db.execute(text("VACUUM ANALYZE currencies"))

        logger.info("Database maintenance completed successfully")
        return {"status": "success", "message": "Database maintenance completed"}

    except Exception as e:
        logger.error(f"Error during database maintenance: {e}")
        return {"status": "failed", "message": str(e)}
    finally:
        db.close()


@celery_app.task
def create_next_month_partition():
    """
    Create a partition for the next month's exchange rate data.
    This task should be scheduled to run near the end of each month.
    """
    logger.info("Starting task to create next month's partition")
    
    # Get a database session
    db = next(get_db())
    
    try:
        today = datetime.now()
        if today.month == 12:
            next_month_year = today.year + 1
            next_month = 1
        else:
            next_month_year = today.year
            next_month = today.month + 1

        if next_month == 12:
            month_after_next_year = next_month_year + 1
            month_after_next = 1
        else:
            month_after_next_year = next_month_year
            month_after_next = next_month + 1

        start_date = datetime(next_month_year, next_month, 1, tzinfo=datetime.timezone.utc)
        end_date = datetime(month_after_next_year, month_after_next, 1, tzinfo=datetime.timezone.utc)

        start_date_str = start_date.isoformat()
        end_date_str = end_date.isoformat()
        
        partition_name = f"exchange_rates_{start_date.strftime('%Y_%m')}"

        check_query = text(f"""
            SELECT EXISTS (
                SELECT 1 FROM pg_tables 
                WHERE tablename = '{partition_name}'
            );
        """)
        
        partition_exists = db.execute(check_query).scalar()
        
        if partition_exists:
            logger.info(f"Partition {partition_name} already exists, skipping creation")
            return {"status": "skipped", "message": f"Partition {partition_name} already exists"}
        
        # Create the partition
        db.execute(text(f"""
            CREATE TABLE {partition_name} PARTITION OF exchange_rates
            FOR VALUES FROM ('{start_date_str}') TO ('{end_date_str}');
        """))
        
        logger.info(f"Successfully created partition {partition_name} for next month")
        return {
            "status": "success", 
            "partition": partition_name,
            "period": f"{start_date_str} to {end_date_str}"
        }
        
    except Exception as e:
        logger.error(f"Error creating next month's partition: {e}")
        return {"status": "failed", "message": str(e)}
    finally:
        db.close()