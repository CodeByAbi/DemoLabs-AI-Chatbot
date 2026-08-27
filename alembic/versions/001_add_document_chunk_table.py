"""Add document_chunk table for PDF embeddings

Revision ID: add_document_chunk_table
Revises: 001_create_faq_table
Create Date: 2025-10-20 10:00:00.000000

This migration creates the bot.document_chunk table for storing
PDF document chunks with embeddings for RAG retrieval.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_document_chunk_table'
down_revision = '001_create_faq_table'  # Depends on FAQ table creation
branch_labels = None
depends_on = None


def upgrade():
    """
    Create document_chunk table with embedding and chunking metadata.
    """
    # Create document_chunk table
    op.create_table(
        'document_chunk',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('document_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('dataset_id', postgresql.UUID(as_uuid=True), nullable=False),
        
        # Chunk content and metadata
        sa.Column('chunk_text', sa.Text(), nullable=False),
        sa.Column('chunk_index', sa.Integer(), nullable=False),
        sa.Column('chunk_size', sa.Integer(), nullable=False),
        
        # Page information
        sa.Column('page_number', sa.Integer(), nullable=True),
        sa.Column('page_range', sa.String(), nullable=True),
        
        # Embedding and chunking strategy
        sa.Column('embedding', postgresql.ARRAY(sa.Float()), nullable=True),
        sa.Column('chunking_strategy', sa.String(), server_default='recursive'),
        sa.Column('overlap_size', sa.Integer(), server_default='0'),
        
        # Metadata for context
        sa.Column('section_title', sa.String(), nullable=True),
        sa.Column('metadata', sa.Text(), nullable=True),
        
        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', sa.Text(), nullable=True),
        sa.Column('updated_by', sa.Text(), nullable=True),
        
        # Foreign key to document table
        sa.ForeignKeyConstraint(['document_id'], ['bot.document.id'], ondelete='CASCADE', onupdate='CASCADE'),
        
        schema='bot'
    )
    
    # Create indexes for efficient querying
    op.create_index(
        'idx_document_chunk_document_id',
        'document_chunk',
        ['document_id'],
        schema='bot'
    )
    
    op.create_index(
        'idx_document_chunk_dataset_id',
        'document_chunk',
        ['dataset_id'],
        schema='bot'
    )
    
    op.create_index(
        'idx_document_chunk_chunk_index',
        'document_chunk',
        ['document_id', 'chunk_index'],
        schema='bot'
    )
    
    # Create index for page number queries
    op.create_index(
        'idx_document_chunk_page_number',
        'document_chunk',
        ['page_number'],
        schema='bot',
        postgresql_where=sa.text('page_number IS NOT NULL')
    )


def downgrade():
    """
    Drop document_chunk table and related indexes.
    """
    # Drop indexes
    op.drop_index('idx_document_chunk_page_number', table_name='document_chunk', schema='bot')
    op.drop_index('idx_document_chunk_chunk_index', table_name='document_chunk', schema='bot')
    op.drop_index('idx_document_chunk_dataset_id', table_name='document_chunk', schema='bot')
    op.drop_index('idx_document_chunk_document_id', table_name='document_chunk', schema='bot')
    
    # Drop table
    op.drop_table('document_chunk', schema='bot')
