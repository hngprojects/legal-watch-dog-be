"""Merge migration heads - Billings

Revision ID: e24deccf53ec
Revises: 639ff4afb64a, ae35b7ce2a8c
Create Date: 2025-11-27 10:12:49.731690

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e24deccf53ec'
down_revision: Union[str, Sequence[str], None] = ('639ff4afb64a', 'ae35b7ce2a8c')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
