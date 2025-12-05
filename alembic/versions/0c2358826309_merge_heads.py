"""merge manual ticket and role templates migrations

Revision ID: 0c2358826309
Revises: 7810240dba0c, a249039be841
Create Date: 2025-12-05 14:24:25.176250

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0c2358826309'
down_revision: Union[str, Sequence[str], None] = ('7810240dba0c', 'a249039be841')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
