"""merge heads

Revision ID: ae35b7ce2a8c
Revises: f83e60264169, fc7fbd2ffac5
Create Date: 2025-11-26 14:53:36.700769

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ae35b7ce2a8c'
down_revision: Union[str, Sequence[str], None] = ('f83e60264169', 'fc7fbd2ffac5')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
