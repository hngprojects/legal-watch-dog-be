"""empty message

Revision ID: 5c08c6744f79
Revises: a8109c8c21c0, d615ad7aed6e
Create Date: 2025-11-25 19:54:46.466483

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5c08c6744f79'
down_revision: Union[str, Sequence[str], None] = ('a8109c8c21c0', 'd615ad7aed6e')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
