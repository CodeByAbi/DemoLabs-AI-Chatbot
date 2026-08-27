"""
Database models for document storage with embeddings
"""
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Integer, BigInteger
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
import uuid

from app.db.session import Base


class Document(Base):
    """
    Document model for storing PDF documents with metadata.
    Schema: bot.document
    """
    __tablename__ = "document"
    __table_args__ = {"schema": "bot"}
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String, nullable=False)
    content = Column(Text, nullable=True)
    file_name = Column(String, nullable=False)
    file_url = Column(String, nullable=False)
    number_of_pages = Column(BigInteger, default=0)
    dataset_id = Column(UUID(as_uuid=True), nullable=False)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    created_by = Column(Text, nullable=True)
    updated_by = Column(Text, nullable=True)
    
    def __repr__(self):
        return f"<Document(id={self.id}, title={self.title}, pages={self.number_of_pages})>"


class DocumentChunk(Base):
    """
    Document chunks for storing PDF content chunks with embeddings.
    This enables efficient RAG retrieval from large documents.
    Schema: bot.document_chunk
    """
    __tablename__ = "document_chunk"
    __table_args__ = {"schema": "bot"}
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey('bot.document.id', ondelete='CASCADE'), nullable=False)
    dataset_id = Column(UUID(as_uuid=True), nullable=False)
    
    # Chunk content and metadata
    chunk_text = Column(Text, nullable=False)
    chunk_index = Column(Integer, nullable=False)  # Order of chunk in document
    chunk_size = Column(Integer, nullable=False)  # Character count of chunk
    
    # Page information
    page_number = Column(Integer, nullable=True)  # Page number where chunk starts
    page_range = Column(String, nullable=True)  # e.g., "1-2" if chunk spans multiple pages
    
    # Embedding and chunking strategy
    embedding = Column(Vector(1536), nullable=True)  # Vector embedding for RAG
    chunking_strategy = Column(String, default="recursive")  # recursive, fixed, semantic, etc.
    overlap_size = Column(Integer, default=0)  # Characters overlapping with previous chunk
    
    # Metadata for context
    section_title = Column(String, nullable=True)  # Section/chapter title if detected
    chunk_metadata = Column(Text, nullable=True)  # JSON metadata (e.g., fonts, styles, tables)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    created_by = Column(Text, nullable=True)
    updated_by = Column(Text, nullable=True)
    
    def __repr__(self):
        return f"<DocumentChunk(id={self.id}, document_id={self.document_id}, chunk_index={self.chunk_index})>"
