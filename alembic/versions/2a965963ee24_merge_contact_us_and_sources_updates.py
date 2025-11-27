"""merge contact_us and sources updates

Revision ID: 2a965963ee24
Revises: b52cbc0b1765, e40a68f35eaa
Create Date: 2025-11-28 00:28:22.121525

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2a965963ee24'
down_revision: Union[str, Sequence[str], None] = ('b52cbc0b1765', 'e40a68f35eaa')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
