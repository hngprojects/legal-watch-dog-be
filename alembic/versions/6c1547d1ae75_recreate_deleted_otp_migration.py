"""Recreate deleted OTP migration

Revision ID: 6c1547d1ae75
Revises: ee1f19980ca8
Create Date: 2025-11-21 08:06:23.968952

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6c1547d1ae75'
down_revision: Union[str, Sequence[str], None] = 'ee1f19980ca8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
