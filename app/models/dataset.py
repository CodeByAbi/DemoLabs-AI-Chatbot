"""
Dataset model for master.dataset table
"""
from sqlalchemy import Column, String, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import uuid

Base = declarative_base()


class Dataset(Base):
    """Dataset model for master.dataset table"""
    
    __tablename__ = "dataset"
    __table_args__ = {"schema": "master"}
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    type = Column(Text, nullable=False, default='faq')
    description = Column(Text, nullable=True)
    status = Column(String, nullable=False, default='on progress')
    created_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, nullable=True)
    deleted_at = Column(DateTime, nullable=True)
    created_by = Column(Text, nullable=True)
    updated_by = Column(Text, nullable=True)
