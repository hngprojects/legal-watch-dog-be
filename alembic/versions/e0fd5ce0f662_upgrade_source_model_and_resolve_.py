"""upgrade source model and resolve alembic migrations

Revision ID: e0fd5ce0f662
Revises: 2327754e258e, 8db953970cc0
Create Date: 2025-11-26 11:45:13.810955

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e0fd5ce0f662'
down_revision: Union[str, Sequence[str], None] = ('2327754e258e', '8db953970cc0')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
