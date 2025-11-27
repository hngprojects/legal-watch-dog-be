"""merge heads

Revision ID: f83e60264169
Revises: 03db9267c449, 92b6d9686574
Create Date: 2025-11-26 14:51:19.141063

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f83e60264169'
down_revision: Union[str, Sequence[str], None] = ('03db9267c449', '92b6d9686574')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
