"""Merge multiple heads

Revision ID: 8f0dc85e641e
Revises: 174d354d4a7b, a8109c8c21c0
Create Date: 2025-11-25 16:49:49.437189

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8f0dc85e641e'
down_revision: Union[str, Sequence[str], None] = ('174d354d4a7b', 'a8109c8c21c0')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
