"""merge multiple heads

Revision ID: fc7fbd2ffac5
Revises: 8978f9d37aea, b398f6b7c7db
Create Date: 2025-11-26 03:36:22.436443

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fc7fbd2ffac5'
down_revision: Union[str, Sequence[str], None] = ('8978f9d37aea', 'b398f6b7c7db')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
