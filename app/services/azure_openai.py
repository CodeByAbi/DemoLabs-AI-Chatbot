"""
Azure OpenAI service for generating embeddings
"""
import logging
from typing import List, Optional
from openai import AzureOpenAI

from app.core.config import settings

logger = logging.getLogger(__name__)


class AzureOpenAIService:
    """
    Service for interacting with Azure OpenAI API.
    """
    
    def __init__(self):
        """Initialize Azure OpenAI client."""
        self.client = AzureOpenAI(
            api_key=settings.AZURE_OPENAI_API_KEY,
            api_version=settings.AZURE_OPENAI_API_VERSION,
            azure_endpoint=settings.AZURE_OPENAI_ENDPOINT
        )
        self.embedding_deployment = settings.AZURE_OPENAI_EMBEDDING_DEPLOYMENT
        self.embedding_model = settings.AZURE_OPENAI_EMBEDDING_MODEL
    
    def generate_embedding(self, text: str) -> Optional[List[float]]:
        """
        Generate embedding for a single text.
        
        Args:
            text: Text to generate embedding for
            
        Returns:
            List of floats representing the embedding vector
        """
        try:
            response = self.client.embeddings.create(
                input=text,
                model=self.embedding_deployment
            )
            
            embedding = response.data[0].embedding
            logger.info(f"Generated embedding with dimension: {len(embedding)}")
            return embedding
            
        except Exception as e:
            logger.error(f"Error generating embedding: {str(e)}", exc_info=True)
            return None
    
    def generate_embeddings_batch(self, texts: List[str]) -> Optional[List[List[float]]]:
        """
        Generate embeddings for multiple texts in batch.
        
        Args:
            texts: List of texts to generate embeddings for
            
        Returns:
            List of embedding vectors
        """
        try:
            if not texts:
                return []
            
            response = self.client.embeddings.create(
                input=texts,
                model=self.embedding_deployment
            )
            
            embeddings = [item.embedding for item in response.data]
            logger.info(f"Generated {len(embeddings)} embeddings in batch")
            return embeddings
            
        except Exception as e:
            logger.error(f"Error generating batch embeddings: {str(e)}", exc_info=True)
            return None


# Create global instance
azure_openai_service = AzureOpenAIService()
