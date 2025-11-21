"""merge migration heads

Revision ID: 5e15e49b8a3a
Revises: 6057adb630ca, d8683693bd9c
Create Date: 2025-11-21 14:00:21.026760

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5e15e49b8a3a'
down_revision: Union[str, Sequence[str], None] = ('6057adb630ca', 'd8683693bd9c')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
