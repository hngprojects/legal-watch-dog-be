"""merge_heads

Revision ID: 1cdaa4ddd6e4
Revises: 03db9267c449, c898c3a02ef8
Create Date: 2025-11-28 21:31:59.723851

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1cdaa4ddd6e4'
down_revision: Union[str, Sequence[str], None] = ('03db9267c449', 'c898c3a02ef8')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
