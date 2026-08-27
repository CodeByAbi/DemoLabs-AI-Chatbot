"""
FastAPI Main Application
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.v1.endpoints import queue, persona, text_to_sql

# Create FastAPI app
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description=settings.DESCRIPTION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
)

# Configure CORS
cors_origins = settings.get_cors_origins()
if cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Include API routers
app.include_router(
    queue.router,
    prefix=f"{settings.API_V1_STR}/queue",
    tags=["Queue Management"]
)

app.include_router(
    persona.router,
    prefix=f"{settings.API_V1_STR}/persona",
    tags=["Persona"]
)

app.include_router(
    text_to_sql.router,
    prefix=f"{settings.API_V1_STR}",
    tags=["Text-to-SQL"]
)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Demo Lab Chatbot Orchestrator API",
        "version": settings.VERSION,
        "docs": f"{settings.API_V1_STR}/docs",
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "fastapi",
        "version": settings.VERSION,
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )
