"""Remove OTP table

Revision ID: ee1f19980ca8
Revises: 7b5240df75f9
Create Date: 2025-11-21 08:04:36.464576

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ee1f19980ca8'
down_revision: Union[str, Sequence[str], None] = '7b5240df75f9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
