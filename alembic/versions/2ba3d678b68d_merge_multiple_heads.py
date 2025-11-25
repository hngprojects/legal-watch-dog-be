"""Merge multiple heads

Revision ID: 2ba3d678b68d
Revises: 1cac4059df78, a8109c8c21c0
Create Date: 2025-11-25 21:06:59.631868

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2ba3d678b68d'
down_revision: Union[str, Sequence[str], None] = ('1cac4059df78', 'a8109c8c21c0')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
