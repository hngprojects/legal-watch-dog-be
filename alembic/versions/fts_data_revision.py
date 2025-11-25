"""Add full-text search to data_revision table

Revision ID: fts_data_revision
Revises: a8109c8c21c0
Create Date: 2025-11-21

Alembic migration for DATA_REVISION table with TSVECTOR and trigger.
"""

revision = 'fts_data_revision'
down_revision = 'a8109c8c21c0'
branch_labels = None
depends_on = None
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

def upgrade():
    # Add search_vector column to existing data_revision table
    op.add_column('data_revision', sa.Column('search_vector', postgresql.TSVECTOR, nullable=True))
    
    # Create GIN index for full-text search
    op.create_index('idx_data_revision_search_vector', 'data_revision', ['search_vector'], postgresql_using='gin')

    # Add trigger for search_vector auto-update
    op.execute(open('alembic/versions/trigger_update_data_revision_search_vector.sql').read())


def downgrade():
    # Drop trigger and function
    op.execute('DROP TRIGGER IF EXISTS trg_update_data_revision_search_vector ON data_revision;')
    op.execute('DROP FUNCTION IF EXISTS update_data_revision_search_vector CASCADE;')
    
    # Drop index and column
    op.drop_index('idx_data_revision_search_vector', table_name='data_revision')
    op.drop_column('data_revision', 'search_vector')
