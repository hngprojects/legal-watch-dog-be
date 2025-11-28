"""make jurisdiction_id and source_id nullable

Revision ID: 6631705199ed
Revises: 3e7e5f7ae4aa
Create Date: 2025-11-23 03:46:24.863420

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6631705199ed'
down_revision: Union[str, Sequence[str], None] = '3e7e5f7ae4aa'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
