"""merge heads: billing & change_diff

Revision ID: 8978f9d37aea
Revises: 03db9267c449, a8109c8c21c0
Create Date: 2025-11-25 22:35:21.361778

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8978f9d37aea'
down_revision: Union[str, Sequence[str], None] = ('03db9267c449', 'a8109c8c21c0')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
