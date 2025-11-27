"""fix organization deleted_at with correct defaults

Revision ID: b7c40d70aa47
Revises: 639ff4afb64a
Create Date: 2025-11-27 23:26:15.109119

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7c40d70aa47'
down_revision: Union[str, Sequence[str], None] = '639ff4afb64a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('organizations', 
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True)
    )
    
    # Set all existing records to have deleted_at = NULL
    op.execute("UPDATE organizations SET deleted_at = NULL")


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('organizations', 'deleted_at')
