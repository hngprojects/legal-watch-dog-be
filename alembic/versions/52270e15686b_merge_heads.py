"""merge heads

Revision ID: 52270e15686b
Revises: 924acaf3d7b8, d5328ba9783c, f661a36459ec
Create Date: 2025-11-28 17:35:47.831003

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '52270e15686b'
down_revision: Union[str, Sequence[str], None] = ('924acaf3d7b8', 'd5328ba9783c', 'f661a36459ec')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
