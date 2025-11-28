"""Merge multiple heads

Revision ID: cd1001b9f059
Revises: 6631705199ed, e24deccf53ec, e40a68f35eaa
Create Date: 2025-11-28 02:29:28.761366

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cd1001b9f059'
down_revision: Union[str, Sequence[str], None] = ('6631705199ed', 'e24deccf53ec', 'e40a68f35eaa')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
