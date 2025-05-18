"""Repository for data synchronization jobs."""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Union, Any

import boto3
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError

from src.data.dynamodb import get_dynamodb_client
from src.models.sync import SyncJob, SyncStatus, SyncType
from src.utils.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class SyncJobRepository:
    """Repository for sync jobs in DynamoDB."""

    def __init__(self):
        """Initialize the repository."""
        self.dynamodb = get_dynamodb_client()
        self.table_name = settings.dynamodb_sync_jobs_table
    
    def create(self, sync_job: SyncJob) -> SyncJob:
        """
        Create a new sync job.
        
        Args:
            sync_job: The sync job to create
            
        Returns:
            SyncJob: The created sync job
        """
        item = sync_job.to_dynamodb_item()
        try:
            self.dynamodb.put_item(self.table_name, item)
            return sync_job
        except ClientError as e:
            logger.error(f"Error creating sync job: {e}")
            raise
    
    def get_by_id(self, job_id: str) -> Optional[SyncJob]:
        """
        Get a sync job by ID.
        
        Args:
            job_id: The job ID
            
        Returns:
            Optional[SyncJob]: The sync job, or None if not found
        """
        key = {"job_id": job_id}
        
        try:
            item = self.dynamodb.get_item(self.table_name, key)
            if item:
                return SyncJob.from_dynamodb_item(item)
            return None
        except ClientError as e:
            logger.error(f"Error getting sync job: {e}")
            raise
    
    def get_jobs_by_user(self, user_id: str, limit: int = 100) -> List[SyncJob]:
        """
        Get sync jobs for a user.
        
        Args:
            user_id: The user ID
            limit: Maximum number of jobs to return
            
        Returns:
            List[SyncJob]: The list of sync jobs
        """
        try:
            result = self.dynamodb.query(
                table_name=self.table_name,
                index_name="UserStatusIndex",
                key_condition_expression=Key("user_id").eq(user_id),
                expression_attribute_values={},
                limit=limit
            )
            
            items = result.get("Items", [])
            return [SyncJob.from_dynamodb_item(item) for item in items]
        except ClientError as e:
            logger.error(f"Error querying sync jobs by user: {e}")
            raise
    
    def get_jobs_by_user_and_status(
        self, 
        user_id: str, 
        status: SyncStatus,
        limit: int = 100
    ) -> List[SyncJob]:
        """
        Get sync jobs for a user with a specific status.
        
        Args:
            user_id: The user ID
            status: The job status
            limit: Maximum number of jobs to return
            
        Returns:
            List[SyncJob]: The list of sync jobs
        """
        try:
            result = self.dynamodb.query(
                table_name=self.table_name,
                index_name="UserStatusIndex",
                key_condition_expression=Key("user_id").eq(user_id) & Key("status").eq(status.value),
                expression_attribute_values={},
                limit=limit
            )
            
            items = result.get("Items", [])
            return [SyncJob.from_dynamodb_item(item) for item in items]
        except ClientError as e:
            logger.error(f"Error querying sync jobs by user and status: {e}")
            raise
    
    def get_pending_scheduled_jobs(self, limit: int = 100) -> List[SyncJob]:
        """
        Get pending scheduled jobs that are due.
        
        Args:
            limit: Maximum number of jobs to return
            
        Returns:
            List[SyncJob]: The list of pending scheduled jobs
        """
        now = datetime.utcnow().isoformat()
        
        try:
            result = self.dynamodb.query(
                table_name=self.table_name,
                index_name="StatusScheduledIndex",
                key_condition_expression=Key("status").eq(SyncStatus.PENDING.value) & 
                                          Key("scheduled_time").lte(now),
                expression_attribute_values={},
                limit=limit
            )
            
            items = result.get("Items", [])
            return [SyncJob.from_dynamodb_item(item) for item in items]
        except ClientError as e:
            logger.error(f"Error querying pending scheduled jobs: {e}")
            raise
    
    def get_failed_jobs_for_retry(self, limit: int = 100) -> List[SyncJob]:
        """
        Get failed jobs that are eligible for retry.
        
        Args:
            limit: Maximum number of jobs to return
            
        Returns:
            List[SyncJob]: The list of failed jobs eligible for retry
        """
        try:
            result = self.dynamodb.query(
                table_name=self.table_name,
                index_name="StatusScheduledIndex",
                key_condition_expression=Key("status").eq(SyncStatus.FAILED.value),
                expression_attribute_values={},
                limit=limit
            )
            
            items = result.get("Items", [])
            jobs = [SyncJob.from_dynamodb_item(item) for item in items]
            
            # Filter for retryable jobs
            retryable_jobs = [job for job in jobs if job.is_retryable()]
            
            return retryable_jobs
        except ClientError as e:
            logger.error(f"Error querying failed jobs for retry: {e}")
            raise
    
    def update(self, sync_job: SyncJob) -> SyncJob:
        """
        Update an existing sync job.
        
        Args:
            sync_job: The sync job to update
            
        Returns:
            SyncJob: The updated sync job
        """
        sync_job.updated_at = datetime.utcnow()
        item = sync_job.to_dynamodb_item()
        
        try:
            self.dynamodb.put_item(self.table_name, item)
            return sync_job
        except ClientError as e:
            logger.error(f"Error updating sync job: {e}")
            raise
    
    def update_status(
        self, 
        job_id: str, 
        status: SyncStatus,
        error_message: Optional[str] = None
    ) -> Optional[SyncJob]:
        """
        Update the status of a sync job.
        
        Args:
            job_id: The job ID
            status: The new status
            error_message: Error message if the job failed
            
        Returns:
            Optional[SyncJob]: The updated sync job, or None if not found
        """
        # Get the existing job
        job = self.get_by_id(job_id)
        if not job:
            return None
        
        # Update based on status
        if status == SyncStatus.IN_PROGRESS:
            job.record_start()
        elif status == SyncStatus.COMPLETED:
            job.record_completion(status)
        elif status == SyncStatus.FAILED:
            job.record_failure(error_message or "Unknown error")
        else:
            job.status = status
            job.updated_at = datetime.utcnow()
            if error_message:
                job.error_message = error_message
        
        # Save the updated job
        return self.update(job)
    
    def delete(self, job_id: str) -> bool:
        """
        Delete a sync job.
        
        Args:
            job_id: The job ID
            
        Returns:
            bool: True if the deletion was successful
        """
        key = {"job_id": job_id}
        
        try:
            self.dynamodb.delete_item(self.table_name, key)
            return True
        except ClientError as e:
            logger.error(f"Error deleting sync job: {e}")
            raise
    
    def delete_jobs_by_user(self, user_id: str) -> int:
        """
        Delete all sync jobs for a user.
        
        Args:
            user_id: The user ID
            
        Returns:
            int: The number of deleted jobs
        """
        try:
            # Get all jobs for the user
            jobs = self.get_jobs_by_user(user_id)
            
            # Delete them one by one
            count = 0
            for job in jobs:
                self.delete(job.job_id)
                count += 1
            
            return count
        except ClientError as e:
            logger.error(f"Error deleting sync jobs for user: {e}")
            raise


# Singleton instance
_sync_job_repository: Optional[SyncJobRepository] = None


def get_sync_job_repository() -> SyncJobRepository:
    """
    Get a singleton instance of the sync job repository.
    
    Returns:
        SyncJobRepository: The sync job repository
    """
    global _sync_job_repository
    if _sync_job_repository is None:
        _sync_job_repository = SyncJobRepository()
    return _sync_job_repository 