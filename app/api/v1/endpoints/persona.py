"""
API endpoints for persona management and preview
"""
from typing import Optional
from fastapi import APIRouter, HTTPException, status, Path, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.db.session import SessionLocal
from app.models.persona import Persona
from app.services.azure_openai_chat import azure_openai_chat_service
from app.core.security import get_api_key

router = APIRouter()


class PersonaPreviewResponse(BaseModel):
    """Schema for persona preview response."""
    persona_id: str
    persona_name: str
    persona_description: Optional[str]
    preview_question: str
    preview_answer: str
    status: str


class PersonaDetailResponse(BaseModel):
    """Schema for persona detail response."""
    id: str
    name: str
    prompt: str
    description: Optional[str]
    created_at: Optional[str]
    updated_at: Optional[str]


class CustomQuestionRequest(BaseModel):
    """Schema for custom question request."""
    custom_question: str = Field(..., description="Custom question to ask the persona")


@router.get(
    "/preview/{persona_id}",
    response_model=PersonaPreviewResponse,
    summary="Get Persona Preview",
    description="Generate a preview response for a persona based on their prompt"
)
async def get_persona_preview(
    persona_id: str = Path(..., description="UUID of the persona"),
    api_key: str = Depends(get_api_key)
) -> PersonaPreviewResponse:
    """
    Generate a preview response for a specific persona.
    
    This endpoint:
    1. Fetches the persona from database by ID
    2. Uses Azure OpenAI to generate a response to "Hi, who are you?"
    3. Returns the preview with question and answer
    
    The response is generated based on the persona's prompt which defines
    their behavior, tone, and characteristics.
    
    Args:
        persona_id: UUID of the persona
        
    Returns:
        PersonaPreviewResponse with preview question and answer
        
    Raises:
        404: Persona not found
        500: Error generating preview
    """
    db: Session = SessionLocal()
    
    try:
        # Fetch persona from database
        persona = db.query(Persona).filter(
            and_(
                Persona.id == persona_id,
                Persona.deleted_at.is_(None)  # Only active personas
            )
        ).first()
        
        if not persona:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Persona with id {persona_id} not found"
            )
        
        # Generate preview using Azure OpenAI
        preview_question = "Hi, who are you?"
        
        preview_result = azure_openai_chat_service.generate_persona_preview(
            persona_name=persona.name,
            persona_prompt=persona.prompt,
            preview_question=preview_question
        )
        
        if not preview_result:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to generate preview response"
            )
        
        return PersonaPreviewResponse(
            persona_id=str(persona.id),
            persona_name=persona.name,
            persona_description=persona.description,
            preview_question=preview_result["question"],
            preview_answer=preview_result["answer"],
            status="success"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating persona preview: {str(e)}"
        )
    finally:
        db.close()


@router.get(
    "/{persona_id}",
    response_model=PersonaDetailResponse,
    summary="Get Persona Details",
    description="Retrieve complete details of a persona"
)
async def get_persona_details(
    persona_id: str = Path(..., description="UUID of the persona"),
    api_key: str = Depends(get_api_key)
) -> PersonaDetailResponse:
    """
    Get detailed information about a specific persona.
    
    Args:
        persona_id: UUID of the persona
        
    Returns:
        PersonaDetailResponse with all persona details
        
    Raises:
        404: Persona not found
    """
    db: Session = SessionLocal()
    
    try:
        persona = db.query(Persona).filter(
            and_(
                Persona.id == persona_id,
                Persona.deleted_at.is_(None)
            )
        ).first()
        
        if not persona:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Persona with id {persona_id} not found"
            )
        
        return PersonaDetailResponse(
            id=str(persona.id),
            name=persona.name,
            prompt=persona.prompt,
            description=persona.description,
            created_at=persona.created_at.isoformat() if persona.created_at else None,
            updated_at=persona.updated_at.isoformat() if persona.updated_at else None
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving persona: {str(e)}"
        )
    finally:
        db.close()


@router.post(
    "/preview/{persona_id}/custom",
    response_model=PersonaPreviewResponse,
    summary="Get Custom Persona Preview",
    description="Generate a preview response with a custom question"
)
async def get_custom_persona_preview(
    persona_id: str = Path(..., description="UUID of the persona"),
    request: CustomQuestionRequest = None,
    api_key: str = Depends(get_api_key)
) -> PersonaPreviewResponse:
    """
    Generate a preview response for a persona with a custom question.
    
    Args:
        persona_id: UUID of the persona
        custom_question: Custom question to ask the persona
        
    Returns:
        PersonaPreviewResponse with custom question and answer
        
    Raises:
        404: Persona not found
        500: Error generating preview
    """
    db: Session = SessionLocal()
    
    try:
        # Fetch persona from database
        persona = db.query(Persona).filter(
            and_(
                Persona.id == persona_id,
                Persona.deleted_at.is_(None)
            )
        ).first()
        
        if not persona:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Persona with id {persona_id} not found"
            )
        
        # Generate preview with custom question
        preview_result = azure_openai_chat_service.generate_persona_preview(
            persona_name=persona.name,
            persona_prompt=persona.prompt,
            preview_question=request.custom_question
        )
        
        if not preview_result:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to generate preview response"
            )
        
        return PersonaPreviewResponse(
            persona_id=str(persona.id),
            persona_name=persona.name,
            persona_description=persona.description,
            preview_question=preview_result["question"],
            preview_answer=preview_result["answer"],
            status="success"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating custom preview: {str(e)}"
        )
    finally:
        db.close()
