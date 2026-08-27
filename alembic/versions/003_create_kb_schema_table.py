"""Add schema_name and dataset_id to bot.table, create kb_schema for transaction tables

This migration:
1. Adds schema_name and dataset_id columns to bot.table (table metadata)
2. Creates kb_schema schema for storing actual transaction/business tables (orders, products, users, etc.)

bot.table stores METADATA about tables (names, descriptions, embeddings)
kb_schema stores ACTUAL transaction data that SQL queries will target

Revision ID: 003_create_kb_schema_table
Revises: 002_add_text_to_sql_embeddings
Create Date: 2025-10-23 15:00:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '003_create_kb_schema_table'
down_revision = '002_add_text_to_sql_embeddings'
branch_labels = None
depends_on = None


def upgrade():
    """Add schema_name and dataset_id to bot.table, create kb_schema for transaction tables"""
    
    # Create kb_schema for storing actual transaction tables (orders, products, users, etc.)
    op.execute("CREATE SCHEMA IF NOT EXISTS kb_schema")
    
    # Add new columns to bot.table
    # schema_name: which schema the table exists in (e.g., 'kb_schema', 'public')
    # dataset_id: link table metadata to specific datasets
    op.add_column(
        'table',
        sa.Column('schema_name', sa.Text(), nullable=True),
        schema='bot'
    )
    
    op.add_column(
        'table',
        sa.Column('dataset_id', postgresql.UUID(as_uuid=True), nullable=True),  # Nullable first for migration
        schema='bot'
    )
    
    # Set default schema_name for existing records
    op.execute("UPDATE bot.table SET schema_name = 'kb_schema' WHERE schema_name IS NULL")
    
    # Add foreign key constraint to dataset
    op.create_foreign_key(
        'fk_bot_table_dataset',
        'table', 'dataset',
        ['dataset_id'], ['id'],
        source_schema='bot',
        referent_schema='master',
        ondelete='CASCADE',
        onupdate='CASCADE'
    )
    
    # Create index on dataset_id
    op.create_index(
        'ix_bot_table_dataset_id',
        'table',
        ['dataset_id'],
        schema='bot'
    )


def downgrade():
    """Remove schema_name and dataset_id from bot.table, drop kb_schema"""
    
    # Drop index
    op.drop_index('ix_bot_table_dataset_id', table_name='table', schema='bot')
    
    # Drop foreign key
    op.drop_constraint('fk_bot_table_dataset', 'table', schema='bot', type_='foreignkey')
    
    # Drop columns
    op.drop_column('table', 'dataset_id', schema='bot')
    op.drop_column('table', 'schema_name', schema='bot')
    
    # Note: We don't drop kb_schema as it might contain transaction tables
    # Users should manually drop it if needed
