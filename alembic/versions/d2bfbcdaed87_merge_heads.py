"""merge heads

Revision ID: d2bfbcdaed87
Revises: 6057adb630ca, dd94c68c2ed7
Create Date: 2025-11-21 00:55:52.766143

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd2bfbcdaed87'
down_revision: Union[str, Sequence[str], None] = ('6057adb630ca', 'dd94c68c2ed7')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
