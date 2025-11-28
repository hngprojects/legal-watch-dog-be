"""merge multiple heads again

Revision ID: 30b4f1473666
Revises: e24deccf53ec, e40a68f35eaa
Create Date: 2025-11-28 04:24:54.235958

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '30b4f1473666'
down_revision: Union[str, Sequence[str], None] = ('e24deccf53ec', 'e40a68f35eaa')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
