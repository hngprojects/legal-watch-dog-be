"""Merge heads

Revision ID: bda7ba172dbe
Revises: 03db9267c449, 924acaf3d7b8
Create Date: 2025-11-29 11:18:08.247712

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bda7ba172dbe'
down_revision: Union[str, Sequence[str], None] = ('03db9267c449', '924acaf3d7b8')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
