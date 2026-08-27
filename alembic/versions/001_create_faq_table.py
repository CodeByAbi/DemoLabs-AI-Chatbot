"""
Create bot.faq table with embedding column

Revision ID: 001_create_faq_table
Revises: 
Create Date: 2025-10-20
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001_create_faq_table'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Create bot schema and faq table with embedding column.
    """
    # Create bot schema if it doesn't exist
    op.execute("CREATE SCHEMA IF NOT EXISTS bot")
    
    # Create faq table
    op.create_table(
        'faq',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('question', sa.Text(), nullable=False),
        sa.Column('answer', sa.Text(), nullable=False),
        sa.Column('dataset_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('embedding', postgresql.ARRAY(sa.Float()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', sa.Text(), nullable=True),
        sa.Column('updated_by', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        schema='bot'
    )
    
    # Note: Foreign key constraint commented out as master.dataset table may not exist yet
    # Uncomment this if master.dataset table exists:
    # op.create_foreign_key(
    #     'fk_bot_faq_dataset',
    #     'faq', 'dataset',
    #     ['dataset_id'], ['id'],
    #     source_schema='bot', referent_schema='master',
    #     ondelete='CASCADE', onupdate='CASCADE'
    # )
    
    # Create index on dataset_id for faster lookups
    op.create_index('ix_bot_faq_dataset_id', 'faq', ['dataset_id'], schema='bot')
    
    # Create index on created_at for sorting
    op.create_index('ix_bot_faq_created_at', 'faq', ['created_at'], schema='bot')


def downgrade() -> None:
    """
    Drop faq table and bot schema.
    """
    op.drop_index('ix_bot_faq_created_at', table_name='faq', schema='bot')
    op.drop_index('ix_bot_faq_dataset_id', table_name='faq', schema='bot')
    op.drop_table('faq', schema='bot')
    op.execute("DROP SCHEMA IF EXISTS bot CASCADE")
