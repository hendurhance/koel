from datetime import datetime
from app.utils.cache_manager import CacheManager


class ProgressTracker:
    """
    Track progress of scraping tasks and handle retries.
    Uses Redis to maintain state between task runs.
    """
    
    @staticmethod
    def start_job(job_id: str):
        """Mark a job as started in Redis"""
        now = datetime.now().isoformat()
        job_data = {
            "status": "running",
            "start_time": now,
            "completed_currencies": [],
            "failed_currencies": [],
            "retry_count": 0
        }
        CacheManager.set(f"job:{job_id}", job_data)
        return job_data
    
    @staticmethod
    def get_job_status(job_id: str):
        """Get current status of a job"""
        job_data = CacheManager.get(f"job:{job_id}")
        if job_data:
            return job_data
        return None
    
    @staticmethod
    def mark_currency_complete(job_id: str, currency_code: str):
        """Mark a currency as successfully processed"""
        job_data = ProgressTracker.get_job_status(job_id)
        if job_data:
            if currency_code not in job_data["completed_currencies"]:
                job_data["completed_currencies"].append(currency_code)
            CacheManager.set(f"job:{job_id}", job_data)
    
    @staticmethod
    def mark_currency_failed(job_id: str, currency_code: str):
        """Mark a currency as failed to process"""
        job_data = ProgressTracker.get_job_status(job_id)
        if job_data:
            if currency_code not in job_data["failed_currencies"]:
                job_data["failed_currencies"].append(currency_code)
            CacheManager.set(f"job:{job_id}", job_data)
    
    @staticmethod
    def should_retry_currency(job_id: str, currency_code: str, max_retries: int = 3):
        """Check if a currency should be retried based on its retry count"""
        key = f"retry:{job_id}:{currency_code}"
        retry_count = CacheManager.get(key)
        
        if retry_count is None:
            CacheManager.set(key, "1")
            return True
        
        retry_count = int(retry_count)
        if retry_count < max_retries:
            CacheManager.set(key, str(retry_count + 1))
            return True
        
        return False
    
    @staticmethod
    def complete_job(job_id: str, status: str = "completed"):
        """Mark a job as completed"""
        job_data = ProgressTracker.get_job_status(job_id)
        if job_data:
            job_data["status"] = status
            job_data["end_time"] = datetime.now().isoformat()
            job_data["duration"] = (
                datetime.fromisoformat(job_data["end_time"]) - 
                datetime.fromisoformat(job_data["start_time"])
            ).total_seconds()
            CacheManager.set(f"job:{job_id}", job_data)
        return job_datax