"""merge multiple heads

Revision ID: 6598ba0a4164
Revises: 30b4f1473666, cd1001b9f059
Create Date: 2025-11-28 09:19:16.773053

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6598ba0a4164'
down_revision: Union[str, Sequence[str], None] = ('30b4f1473666', 'cd1001b9f059')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
