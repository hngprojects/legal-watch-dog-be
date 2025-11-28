"""make hashed_password nullable

Revision ID: 84a91f4f3ead
Revises: 639ff4afb64a
Create Date: 2025-11-27 23:37:03.538910
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "84a91f4f3ead"
down_revision: Union[str, Sequence[str], None] = "e40a68f35eaa"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Upgrade schema."""
   
    op.alter_column(
        "users",
        "hashed_password",
        existing_type=sa.VARCHAR(length=255),
        nullable=True,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column(
        "users",
        "hashed_password",
        existing_type=sa.VARCHAR(length=255),
        nullable=False,
    )

