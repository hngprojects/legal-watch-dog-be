"""merge make hashed_password nullable + create contact us table

Revision ID: d9fc6cba6671
Revises: 84a91f4f3ead, e40a68f35eaa
Create Date: 2025-11-28 12:13:33.760968

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd9fc6cba6671'
down_revision: Union[str, Sequence[str], None] = ('84a91f4f3ead', 'e40a68f35eaa')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
