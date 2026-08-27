"""
Webhook Service for External API Integration

This service handles webhook calls to external systems for dataset status updates.
Used by embedding workers to notify external systems when dataset processing is complete.
"""
import logging
import requests
from typing import Dict, Any, Optional
from datetime import datetime

from app.core.config import settings

logger = logging.getLogger(__name__)


class WebhookService:
    """Service for making webhook calls to external APIs"""
    
    def __init__(
        self,
        webhook_base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: Optional[int] = None
    ):
        """
        Initialize webhook service.
        
        Args:
            webhook_base_url: Base URL for webhook endpoints (defaults to settings)
            api_key: API key for authentication (defaults to settings)
            timeout: Request timeout in seconds (defaults to settings)
        """
        self.webhook_base_url = (webhook_base_url or settings.WEBHOOK_BASE_URL).rstrip('/')
        self.api_key = api_key or settings.WEBHOOK_API_KEY
        self.timeout = timeout or settings.WEBHOOK_TIMEOUT
        
    def update_dataset_status(
        self,
        dataset_id: str,
        status: str = "Completed"
    ) -> Dict[str, Any]:
        """
        Update dataset status via webhook.
        
        This method is called by embedding workers after successful processing
        to notify the external system that dataset embedding is complete.
        
        Args:
            dataset_id: UUID of the dataset to update
            status: New status (default: "Completed")
            
        Returns:
            Dict containing success status and response data
        """
        endpoint = f"{self.webhook_base_url}/api/webhook/update-dataset/{dataset_id}"
        
        headers = {
            "x-api-key": self.api_key,
            "Content-Type": "application/json"
        }
        
        payload = {
            "status": status
        }
        
        logger.info(
            f"[Webhook] Calling dataset update webhook for dataset {dataset_id} "
            f"with status '{status}' at {endpoint}"
        )
        
        try:
            start_time = datetime.utcnow()
            
            response = requests.put(
                endpoint,
                json=payload,
                headers=headers,
                timeout=self.timeout
            )
            
            duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            # Check response status
            response.raise_for_status()
            
            logger.info(
                f"[Webhook] ✓ Webhook success for dataset {dataset_id} "
                f"(status: {response.status_code}, duration: {duration_ms:.2f}ms)"
            )
            
            return {
                "success": True,
                "dataset_id": dataset_id,
                "status": status,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
                "response": response.json() if response.content else {}
            }
            
        except requests.exceptions.Timeout as e:
            logger.error(
                f"[Webhook] ✗ Webhook timeout for dataset {dataset_id}: {str(e)}"
            )
            return {
                "success": False,
                "dataset_id": dataset_id,
                "error": "timeout",
                "message": str(e)
            }
            
        except requests.exceptions.HTTPError as e:
            logger.error(
                f"[Webhook] ✗ Webhook HTTP error for dataset {dataset_id}: "
                f"{e.response.status_code} - {str(e)}"
            )
            return {
                "success": False,
                "dataset_id": dataset_id,
                "error": "http_error",
                "status_code": e.response.status_code,
                "message": str(e)
            }
            
        except requests.exceptions.ConnectionError as e:
            logger.error(
                f"[Webhook] ✗ Webhook connection error for dataset {dataset_id}: {str(e)}"
            )
            return {
                "success": False,
                "dataset_id": dataset_id,
                "error": "connection_error",
                "message": str(e)
            }
            
        except Exception as e:
            logger.error(
                f"[Webhook] ✗ Webhook unexpected error for dataset {dataset_id}: {str(e)}",
                exc_info=True
            )
            return {
                "success": False,
                "dataset_id": dataset_id,
                "error": "unknown_error",
                "message": str(e)
            }


# Global service instance
webhook_service = WebhookService()
