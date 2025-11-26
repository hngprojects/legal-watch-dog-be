"""merge heads from dev branch

Revision ID: 2327754e258e
Revises: 8f0dc85e641e, b398f6b7c7db
Create Date: 2025-11-26 06:14:36.638198

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2327754e258e'
down_revision: Union[str, Sequence[str], None] = ('8f0dc85e641e', 'b398f6b7c7db')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
