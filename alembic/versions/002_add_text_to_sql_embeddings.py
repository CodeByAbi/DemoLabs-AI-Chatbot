
"""Add embedding columns to text_to_sql tables

Revision ID: 002_add_text_to_sql_embeddings
Revises: 001_create_faq_table
Create Date: 2025-10-23 08:15:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '002_add_text_to_sql_embeddings'
down_revision = 'add_document_chunk_table'
branch_labels = None
depends_on = None


def upgrade():
    """Add embedding columns to bot.table and bot.text_to_sql"""
    
    # Add embedding column to bot.table
    op.add_column(
        'table',
        sa.Column('embedding', postgresql.ARRAY(sa.Float()), nullable=True),
        schema='bot'
    )
    
    # Add embedding column to bot.text_to_sql
    op.add_column(
        'text_to_sql',
        sa.Column('embedding', postgresql.ARRAY(sa.Float()), nullable=True),
        schema='bot'
    )
    
    # Add indexes for better performance
    op.create_index(
        'ix_bot_table_deleted_at',
        'table',
        ['deleted_at'],
        schema='bot'
    )
    
    op.create_index(
        'ix_bot_text_to_sql_dataset_id',
        'text_to_sql',
        ['dataset_id'],
        schema='bot'
    )
    
    op.create_index(
        'ix_bot_text_to_sql_deleted_at',
        'text_to_sql',
        ['deleted_at'],
        schema='bot'
    )


def downgrade():
    """Remove embedding columns"""
    
    # Drop indexes
    op.drop_index('ix_bot_text_to_sql_deleted_at', table_name='text_to_sql', schema='bot')
    op.drop_index('ix_bot_text_to_sql_dataset_id', table_name='text_to_sql', schema='bot')
    op.drop_index('ix_bot_table_deleted_at', table_name='table', schema='bot')
    
    # Drop columns
    op.drop_column('text_to_sql', 'embedding', schema='bot')
    op.drop_column('table', 'embedding', schema='bot')
