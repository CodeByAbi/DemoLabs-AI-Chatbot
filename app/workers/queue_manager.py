"""
Queue management utilities for inspecting and managing Celery queues
"""
import logging
from typing import Dict, List, Any, Optional
from celery import Celery
from celery.result import AsyncResult
from kombu import Connection

from app.core.celery import celery_app
from app.core.config import settings

logger = logging.getLogger(__name__)


class QueueManager:
    """
    Manager for inspecting and managing Celery queues.
    """
    
    def __init__(self, celery_instance: Celery = None):
        """
        Initialize queue manager.
        
        Args:
            celery_instance: Celery app instance
        """
        self.celery = celery_instance or celery_app
        self.broker_url = settings.CELERY_BROKER_URL
    
    def get_queue_length(self, queue_name: str = "chat_incoming") -> int:
        """
        Get the number of messages in a specific queue.
        
        Args:
            queue_name: Name of the queue to inspect
            
        Returns:
            Number of messages in the queue
        """
        try:
            with Connection(self.broker_url) as conn:
                channel = conn.channel()
                queue = channel.queue_declare(queue=queue_name, passive=True)
                message_count = queue.message_count
                logger.info(f"Queue '{queue_name}' has {message_count} messages")
                return message_count
        except Exception as e:
            logger.error(f"Error getting queue length: {str(e)}")
            return 0
    
    def list_tasks_in_queue(self, queue_name: str = "chat_incoming") -> List[Dict[str, Any]]:
        """
        List all pending tasks in a specific queue.
        
        Args:
            queue_name: Name of the queue to inspect
            
        Returns:
            List of task information dictionaries
        """
        try:
            inspector = self.celery.control.inspect()
            
            # Get reserved tasks (currently being processed)
            reserved = inspector.reserved()
            
            # Get scheduled tasks
            scheduled = inspector.scheduled()
            
            # Get active tasks
            active = inspector.active()
            
            tasks = []
            
            # Process reserved tasks
            if reserved:
                for worker, task_list in reserved.items():
                    for task in task_list:
                        if task.get("delivery_info", {}).get("routing_key") == f"{queue_name}":
                            tasks.append({
                                "task_id": task.get("id"),
                                "task_name": task.get("name"),
                                "worker": worker,
                                "status": "reserved",
                                "args": task.get("args"),
                                "kwargs": task.get("kwargs"),
                            })
            
            # Process active tasks
            if active:
                for worker, task_list in active.items():
                    for task in task_list:
                        if task.get("delivery_info", {}).get("routing_key") == f"{queue_name}":
                            tasks.append({
                                "task_id": task.get("id"),
                                "task_name": task.get("name"),
                                "worker": worker,
                                "status": "active",
                                "args": task.get("args"),
                                "kwargs": task.get("kwargs"),
                                "time_start": task.get("time_start"),
                            })
            
            # Process scheduled tasks
            if scheduled:
                for worker, task_list in scheduled.items():
                    for task in task_list:
                        if task.get("delivery_info", {}).get("routing_key") == f"{queue_name}":
                            tasks.append({
                                "task_id": task.get("request", {}).get("id"),
                                "task_name": task.get("request", {}).get("name"),
                                "worker": worker,
                                "status": "scheduled",
                                "eta": task.get("eta"),
                            })
            
            logger.info(f"Found {len(tasks)} tasks in queue '{queue_name}'")
            return tasks
            
        except Exception as e:
            logger.error(f"Error listing tasks in queue: {str(e)}")
            return []
    
    def get_queue_stats(self, queue_name: str = "chat_incoming") -> Dict[str, Any]:
        """
        Get comprehensive statistics for a queue.
        
        Args:
            queue_name: Name of the queue to inspect
            
        Returns:
            Dictionary with queue statistics
        """
        try:
            inspector = self.celery.control.inspect()
            
            stats = {
                "queue_name": queue_name,
                "message_count": self.get_queue_length(queue_name),
                "active_tasks": 0,
                "reserved_tasks": 0,
                "scheduled_tasks": 0,
                "workers": [],
            }
            
            # Get active workers
            active_workers = inspector.active()
            if active_workers:
                stats["workers"] = list(active_workers.keys())
                stats["worker_count"] = len(active_workers.keys())
            
            # Count task statuses
            active = inspector.active()
            if active:
                for worker, tasks in active.items():
                    stats["active_tasks"] += len([
                        t for t in tasks 
                        if t.get("delivery_info", {}).get("routing_key") == queue_name
                    ])
            
            reserved = inspector.reserved()
            if reserved:
                for worker, tasks in reserved.items():
                    stats["reserved_tasks"] += len([
                        t for t in tasks 
                        if t.get("delivery_info", {}).get("routing_key") == queue_name
                    ])
            
            scheduled = inspector.scheduled()
            if scheduled:
                for worker, tasks in scheduled.items():
                    stats["scheduled_tasks"] += len([
                        t for t in tasks 
                        if t.get("delivery_info", {}).get("routing_key") == queue_name
                    ])
            
            stats["total_pending"] = (
                stats["message_count"] + 
                stats["active_tasks"] + 
                stats["reserved_tasks"]
            )
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting queue stats: {str(e)}")
            return {"error": str(e)}
    
    def purge_queue(self, queue_name: str = "chat_incoming") -> int:
        """
        Purge (clear) all messages from a queue.
        
        Args:
            queue_name: Name of the queue to purge
            
        Returns:
            Number of messages purged
        """
        try:
            with Connection(self.broker_url) as conn:
                channel = conn.channel()
                purged = channel.queue_purge(queue_name)
                logger.warning(f"Purged {purged} messages from queue '{queue_name}'")
                return purged
        except Exception as e:
            logger.error(f"Error purging queue: {str(e)}")
            return 0
    
    def get_task_result(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the result of a completed task.
        
        Args:
            task_id: Task ID to retrieve
            
        Returns:
            Task result information
        """
        try:
            result = AsyncResult(task_id, app=self.celery)
            
            return {
                "task_id": task_id,
                "status": result.status,
                "result": result.result if result.successful() else None,
                "error": str(result.info) if result.failed() else None,
                "ready": result.ready(),
                "successful": result.successful(),
            }
        except Exception as e:
            logger.error(f"Error getting task result: {str(e)}")
            return None


# Create global instance
queue_manager = QueueManager()
