"""
Core configuration and settings module
"""
from typing import List, Optional
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    """
    
    # Project Info
    PROJECT_NAME: str = "Demo Lab Chatbot Orchestrator"
    VERSION: str = "0.1.0"
    DESCRIPTION: str = "FastAPI application with Celery workers"
    API_V1_STR: str = "/api/v1"
    
    # Server Config
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = True
    APP_ENV: str = "development"
    ENVIRONMENT: str = "production"  # "development" or "production" - affects Celery queue creation
    
    # CORS
    BACKEND_CORS_ORIGINS: str = ""

    def get_cors_origins(self) -> List[str]:
        """Parse CORS origins from comma-separated string."""
        if not self.BACKEND_CORS_ORIGINS:
            return []
        return [origin.strip() for origin in self.BACKEND_CORS_ORIGINS.split(",") if origin.strip()]

    # PostgreSQL Database
    POSTGRES_USERNAME: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DATABASE: str = "demolab"
    POSTGRES_ENDPOINT: str = "localhost"
    POSTGRES_PORT: int = 5432
    DATABASE_URL: Optional[str] = None
    
    def get_database_url(self) -> str:
        """Construct database URL from components."""
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return (
            f"postgresql://{self.POSTGRES_USERNAME}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_ENDPOINT}:{self.POSTGRES_PORT}/{self.POSTGRES_DATABASE}"
        )
    
    # Redis
    REDIS_ENDPOINT: str = "localhost"
    REDIS_PASSWORD: Optional[str] = None
    REDIS_PORT: int = 6379
    REDIS_URL: Optional[str] = None
    
    def get_redis_url(self) -> str:
        """Construct Redis URL from components."""
        if self.REDIS_URL:
            return self.REDIS_URL
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_ENDPOINT}:{self.REDIS_PORT}/0"
        return f"redis://{self.REDIS_ENDPOINT}:{self.REDIS_PORT}/0"
    
    # RabbitMQ
    RABBITMQ_USERNAME: str = "guest"
    RABBITMQ_PASSWORD: str = "guest"
    RABBITMQ_UI_ENDPOINT: Optional[str] = None
    RABBITMQ_AMQP_HOST: str = "localhost"
    RABBITMQ_AMQP_PORT: int = 5672
    RABBITMQ_URL: Optional[str] = None
    
    def get_rabbitmq_url(self) -> str:
        """Construct RabbitMQ URL from components."""
        if self.RABBITMQ_URL:
            return self.RABBITMQ_URL
        return (
            f"amqp://{self.RABBITMQ_USERNAME}:{self.RABBITMQ_PASSWORD}"
            f"@{self.RABBITMQ_AMQP_HOST}:{self.RABBITMQ_AMQP_PORT}//"
        )
    
    # Celery
    CELERY_BROKER_URL: Optional[str] = None
    CELERY_RESULT_BACKEND: Optional[str] = None
    
    @property
    def get_celery_broker_url(self) -> str:
        """Get Celery broker URL (RabbitMQ)."""
        return self.CELERY_BROKER_URL or self.get_rabbitmq_url()
    
    @property
    def get_celery_result_backend(self) -> str:
        """Get Celery result backend URL (Redis)."""
        return self.CELERY_RESULT_BACKEND or self.get_redis_url()
    
    # Elasticsearch
    ELASTICSEARCH_USERNAME: str = "elastic"
    ELASTICSEARCH_PASSWORD: str = ""
    ELASTICSEARCH_ENDPOINT: str = "localhost:9200"
    ELASTICSEARCH_URL: Optional[str] = None
    
    def get_elasticsearch_url(self) -> str:
        """Construct Elasticsearch URL from components."""
        if self.ELASTICSEARCH_URL:
            return self.ELASTICSEARCH_URL
        if self.ELASTICSEARCH_PASSWORD:
            return f"http://{self.ELASTICSEARCH_USERNAME}:{self.ELASTICSEARCH_PASSWORD}@{self.ELASTICSEARCH_ENDPOINT}"
        return f"http://{self.ELASTICSEARCH_ENDPOINT}"
    
    # Azure Blob Storage
    AZURE_STORAGE_ACCOUNT_NAME: str = ""
    AZURE_STORAGE_CONTAINER_NAME: str = ""
    AZURE_STORAGE_ACCOUNT_KEY: str = ""
    AZURE_STORAGE_CONNECTION_STRING: Optional[str] = None
    
    # Azure OpenAI
    AZURE_OPENAI_ENDPOINT: str = "https://crayon-chatgpt-4-turbo.openai.azure.com"
    AZURE_OPENAI_API_KEY: str = "a15c3416056b4e6c9f36d72b5c4e61df"
    AZURE_OPENAI_EMBEDDING_DEPLOYMENT: str = "research-ada-vision"
    AZURE_OPENAI_EMBEDDING_MODEL: str = "text-embedding-ada-002"
    AZURE_OPENAI_CHAT_DEPLOYMENT: str = "demolab-gpt-4o-mini"
    AZURE_OPENAI_CHAT_MODEL: str = "gpt-4o-mini"
    AZURE_OPENAI_API_VERSION: str = "2024-02-01"
    
    # Security
    SECRET_KEY: str = "your-secret-key-here-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    API_KEY: str = "fYJqZbnf0Oc8VOoWhWKmTaC1yqwAc7xoxFwdL1p0Ll75sZDSkKFvoXaaagufV5zJ"  # API Key for endpoint authentication
    
    # Webhook Configuration
    WEBHOOK_BASE_URL: str = "https://sse-engine.demo-lab.nawnest.my.id"
    WEBHOOK_API_KEY: str = "62eCYpd99Y2thLBFU4lRcSsp81JCbCmB"
    WEBHOOK_TIMEOUT: int = 30  # seconds
    WEBHOOK_MAX_RETRIES: int = 3
    WEBHOOK_RETRY_DELAY: int = 2  # seconds (exponential backoff)
    
    # Logging
    LOG_LEVEL: str = "INFO"
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )


settings = Settings()

# Update Celery URLs with constructed values
if not settings.CELERY_BROKER_URL:
    settings.CELERY_BROKER_URL = settings.get_celery_broker_url

if not settings.CELERY_RESULT_BACKEND:
    settings.CELERY_RESULT_BACKEND = settings.get_celery_result_backend

if not settings.DATABASE_URL:
    settings.DATABASE_URL = settings.get_database_url()
