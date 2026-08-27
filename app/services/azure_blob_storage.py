"""
Azure Blob Storage Service

This service handles interactions with Azure Blob Storage, including:
- Generating SAS tokens for secure blob access
- Downloading blobs
- Uploading blobs
- Listing blobs in containers
"""
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from io import BytesIO

from azure.storage.blob import BlobServiceClient, generate_blob_sas, BlobSasPermissions
from azure.core.exceptions import AzureError

from app.core.config import settings

logger = logging.getLogger(__name__)


class AzureBlobStorageService:
    """
    Service for interacting with Azure Blob Storage.
    """
    
    def __init__(self):
        """Initialize Azure Blob Storage client."""
        self.account_name = settings.AZURE_STORAGE_ACCOUNT_NAME
        self.account_key = settings.AZURE_STORAGE_ACCOUNT_KEY
        self.container_name = settings.AZURE_STORAGE_CONTAINER_NAME
        self.connection_string = settings.AZURE_STORAGE_CONNECTION_STRING
        
        # Initialize BlobServiceClient
        if self.connection_string:
            self.blob_service_client = BlobServiceClient.from_connection_string(
                self.connection_string
            )
        else:
            # Construct connection string from components
            self.blob_service_client = BlobServiceClient(
                account_url=f"https://{self.account_name}.blob.core.windows.net",
                credential=self.account_key
            )
        
        logger.info(f"Initialized Azure Blob Storage service for account: {self.account_name}")
    
    def generate_sas_token(
        self,
        blob_name: str,
        container_name: Optional[str] = None,
        expiry_hours: int = 1,
        permissions: str = "r"
    ) -> str:
        """
        Generate a SAS token for a blob.
        
        Args:
            blob_name: Name of the blob
            container_name: Container name (uses default if not provided)
            expiry_hours: Token expiry time in hours
            permissions: Permissions string (r=read, w=write, d=delete, l=list)
            
        Returns:
            SAS token string
        """
        try:
            container = container_name or self.container_name
            
            # Generate SAS token
            sas_token = generate_blob_sas(
                account_name=self.account_name,
                account_key=self.account_key,
                container_name=container,
                blob_name=blob_name,
                permission=BlobSasPermissions(read=True) if permissions == "r" else permissions,
                expiry=datetime.utcnow() + timedelta(hours=expiry_hours)
            )
            
            logger.info(f"Generated SAS token for blob: {blob_name} (expires in {expiry_hours}h)")
            return sas_token
            
        except Exception as e:
            logger.error(f"Error generating SAS token for {blob_name}: {str(e)}")
            raise
    
    def get_blob_url_with_sas(
        self,
        blob_name: str,
        container_name: Optional[str] = None,
        expiry_hours: int = 1
    ) -> str:
        """
        Get blob URL with SAS token.
        
        Args:
            blob_name: Name of the blob
            container_name: Container name (uses default if not provided)
            expiry_hours: Token expiry time in hours
            
        Returns:
            Full blob URL with SAS token
        """
        container = container_name or self.container_name
        sas_token = self.generate_sas_token(blob_name, container, expiry_hours)
        
        blob_url = (
            f"https://{self.account_name}.blob.core.windows.net/"
            f"{container}/{blob_name}?{sas_token}"
        )
        
        return blob_url
    
    def parse_blob_url(self, blob_url: str) -> Dict[str, str]:
        """
        Parse Azure Blob Storage URL to extract components.
        
        Args:
            blob_url: Full blob URL
            
        Returns:
            Dict with container_name, blob_name, and base_url
            
        Example:
            Input: https://account.blob.core.windows.net/container/folder/file.pdf
            Output: {
                "container_name": "container",
                "blob_name": "folder/file.pdf",
                "base_url": "https://account.blob.core.windows.net"
            }
        """
        try:
            # Remove query parameters if present
            base_url = blob_url.split('?')[0]
            
            # Parse URL structure: https://{account}.blob.core.windows.net/{container}/{blob_path}
            parts = base_url.replace('https://', '').split('/')
            
            if len(parts) < 3:
                raise ValueError(f"Invalid blob URL format: {blob_url}")
            
            account_domain = parts[0]
            container_name = parts[1]
            blob_name = '/'.join(parts[2:])
            
            return {
                "container_name": container_name,
                "blob_name": blob_name,
                "base_url": f"https://{account_domain}",
                "account_name": account_domain.split('.')[0]
            }
            
        except Exception as e:
            logger.error(f"Error parsing blob URL {blob_url}: {str(e)}")
            raise
    
    def add_sas_to_blob_url(
        self,
        blob_url: str,
        expiry_hours: int = 1
    ) -> str:
        """
        Add SAS token to existing blob URL.
        
        Args:
            blob_url: Original blob URL (with or without SAS)
            expiry_hours: Token expiry time in hours
            
        Returns:
            Blob URL with fresh SAS token
        """
        try:
            # Parse the URL
            parsed = self.parse_blob_url(blob_url)
            
            # Generate new SAS token
            sas_token = self.generate_sas_token(
                blob_name=parsed["blob_name"],
                container_name=parsed["container_name"],
                expiry_hours=expiry_hours
            )
            
            # Construct URL with SAS token
            url_with_sas = (
                f"{parsed['base_url']}/{parsed['container_name']}/"
                f"{parsed['blob_name']}?{sas_token}"
            )
            
            return url_with_sas
            
        except Exception as e:
            logger.error(f"Error adding SAS to blob URL: {str(e)}")
            raise
    
    def download_blob(
        self,
        blob_name: str,
        container_name: Optional[str] = None
    ) -> BytesIO:
        """
        Download blob content to memory.
        
        Args:
            blob_name: Name of the blob
            container_name: Container name (uses default if not provided)
            
        Returns:
            BytesIO object containing blob content
        """
        try:
            container = container_name or self.container_name
            
            blob_client = self.blob_service_client.get_blob_client(
                container=container,
                blob=blob_name
            )
            
            stream = BytesIO()
            blob_client.download_blob().readinto(stream)
            stream.seek(0)
            
            logger.info(f"Downloaded blob: {blob_name} from container: {container}")
            return stream
            
        except AzureError as e:
            logger.error(f"Azure error downloading blob {blob_name}: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error downloading blob {blob_name}: {str(e)}")
            raise
    
    def upload_blob(
        self,
        blob_name: str,
        data: bytes,
        container_name: Optional[str] = None,
        overwrite: bool = True,
        metadata: Optional[Dict[str, str]] = None
    ) -> str:
        """
        Upload data to blob storage.
        
        Args:
            blob_name: Name for the blob
            data: Data to upload
            container_name: Container name (uses default if not provided)
            overwrite: Whether to overwrite existing blob
            metadata: Optional metadata dict
            
        Returns:
            Blob URL
        """
        try:
            container = container_name or self.container_name
            
            blob_client = self.blob_service_client.get_blob_client(
                container=container,
                blob=blob_name
            )
            
            blob_client.upload_blob(
                data,
                overwrite=overwrite,
                metadata=metadata
            )
            
            blob_url = blob_client.url
            
            logger.info(f"Uploaded blob: {blob_name} to container: {container}")
            return blob_url
            
        except AzureError as e:
            logger.error(f"Azure error uploading blob {blob_name}: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error uploading blob {blob_name}: {str(e)}")
            raise
    
    def blob_exists(
        self,
        blob_name: str,
        container_name: Optional[str] = None
    ) -> bool:
        """
        Check if blob exists.
        
        Args:
            blob_name: Name of the blob
            container_name: Container name (uses default if not provided)
            
        Returns:
            True if blob exists, False otherwise
        """
        try:
            container = container_name or self.container_name
            
            blob_client = self.blob_service_client.get_blob_client(
                container=container,
                blob=blob_name
            )
            
            return blob_client.exists()
            
        except Exception as e:
            logger.error(f"Error checking blob existence {blob_name}: {str(e)}")
            return False
    
    def list_blobs(
        self,
        container_name: Optional[str] = None,
        name_starts_with: Optional[str] = None
    ) -> list:
        """
        List blobs in container.
        
        Args:
            container_name: Container name (uses default if not provided)
            name_starts_with: Filter by prefix
            
        Returns:
            List of blob names
        """
        try:
            container = container_name or self.container_name
            
            container_client = self.blob_service_client.get_container_client(container)
            
            blobs = container_client.list_blobs(name_starts_with=name_starts_with)
            
            blob_names = [blob.name for blob in blobs]
            
            logger.info(f"Listed {len(blob_names)} blobs from container: {container}")
            return blob_names
            
        except Exception as e:
            logger.error(f"Error listing blobs in {container}: {str(e)}")
            raise


# Global instance
azure_blob_service = AzureBlobStorageService()
