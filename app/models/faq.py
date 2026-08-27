"""
Database models for bot schema
"""
from sqlalchemy import Column, Text, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector
import uuid

from app.db.session import Base


class FAQ(Base):
    """
    FAQ model for storing question-answer pairs with embeddings.
    Schema: bot.faq
    """
    __tablename__ = "faq"
    __table_args__ = {"schema": "bot"}
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    dataset_id = Column(UUID(as_uuid=True), nullable=False)
    embedding = Column(Vector(1536), nullable=True)  # Vector embedding for RAG
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    created_by = Column(Text, nullable=True)
    updated_by = Column(Text, nullable=True)
    
    def __repr__(self):
        return f"<FAQ(id={self.id}, question={self.question[:50]}...)>"

