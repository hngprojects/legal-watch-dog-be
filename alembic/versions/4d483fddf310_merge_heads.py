"""merge heads

Revision ID: 4d483fddf310
Revises: 924acaf3d7b8, fa7a4d7cccac
Create Date: 2025-11-30 12:17:56.472558

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4d483fddf310'
down_revision: Union[str, Sequence[str], None] = ('924acaf3d7b8', 'fa7a4d7cccac')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None



def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
