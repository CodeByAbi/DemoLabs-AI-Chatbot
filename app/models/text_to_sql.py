"""
Database models for Text-to-SQL functionality
"""
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Integer, BigInteger
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
import uuid

from app.db.session import Base


class Table(Base):
    """
    Table model for storing database table metadata.
    Schema: bot.table (metadata about transaction tables in kb_schema)
    """
    __tablename__ = "table"
    __table_args__ = {"schema": "bot"}
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    schema_name = Column(Text, nullable=True)  # Database schema where table exists (e.g., 'kb_schema')
    dataset_id = Column(UUID(as_uuid=True), nullable=False)  # Link to dataset
    embedding = Column(Vector(1536), nullable=True)  # Embedding for table description
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    created_by = Column(Text, nullable=True)
    updated_by = Column(Text, nullable=True)
    
    def __repr__(self):
        return f"<Table(id={self.id}, name={self.name})>"


class TextToSql(Base):
    """
    Text-to-SQL model for storing question-SQL pairs with embeddings.
    This enables few-shot learning for SQL generation via RAG.
    Schema: bot.text_to_sql
    """
    __tablename__ = "text_to_sql"
    __table_args__ = {"schema": "bot"}
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    question = Column(Text, nullable=False)
    sql_query = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    dataset_id = Column(UUID(as_uuid=True), nullable=False)
    embedding = Column(Vector(1536), nullable=True)  # Embedding for question + description
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    created_by = Column(Text, nullable=True)
    updated_by = Column(Text, nullable=True)
    
    def __repr__(self):
        return f"<TextToSql(id={self.id}, question={self.question[:50]})>"


class TextToSqlTables(Base):
    """
    Junction table linking text_to_sql queries with tables.
    This tracks which tables are used in each SQL query.
    Schema: bot.text_to_sql_tables
    """
    __tablename__ = "text_to_sql_tables"
    __table_args__ = {"schema": "bot"}
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    table_id = Column(UUID(as_uuid=True), ForeignKey('bot.table.id', ondelete='CASCADE'), nullable=False)
    text_to_sql_id = Column(UUID(as_uuid=True), ForeignKey('bot.text_to_sql.id', ondelete='CASCADE'), nullable=False)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    created_by = Column(Text, nullable=True)
    updated_by = Column(Text, nullable=True)
    
    def __repr__(self):
        return f"<TextToSqlTables(id={self.id}, table_id={self.table_id}, text_to_sql_id={self.text_to_sql_id})>"
