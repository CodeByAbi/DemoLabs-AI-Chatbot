"""
Database models for master schema - Persona
"""
from sqlalchemy import Column, String, Text, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid

from app.db.session import Base


class Persona(Base):
    """
    Persona model for storing bot personality configurations.
    Schema: master.persona
    """
    __tablename__ = "persona"
    __table_args__ = {"schema": "master"}
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    prompt = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    created_by = Column(Text, nullable=True)
    updated_by = Column(Text, nullable=True)
    
    def __repr__(self):
        return f"<Persona(id={self.id}, name={self.name})>"
