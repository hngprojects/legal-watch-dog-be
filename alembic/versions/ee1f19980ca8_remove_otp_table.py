"""Remove OTP table

Revision ID: ee1f19980ca8
Revises: 243540ac6fd8
Create Date: 2025-11-21 08:04:36.464576

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ee1f19980ca8'
down_revision: Union[str, Sequence[str], None] = '243540ac6fd8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # If you want to drop the OTP table:
    op.drop_index(op.f("ix_otps_user_id"), table_name="otps")
    op.drop_index(op.f("ix_otps_id"), table_name="otps")
    op.drop_index(op.f("ix_otps_code"), table_name="otps")
    op.drop_table("otps")


def downgrade() -> None:
    """Downgrade schema."""
    # Restore the OTP table if needed
    op.create_table(
        "otps",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=6), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("is_used", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_otps_code"), "otps", ["code"], unique=False)
    op.create_index(op.f("ix_otps_id"), "otps", ["id"], unique=False)
    op.create_index(op.f("ix_otps_user_id"), "otps", ["user_id"], unique=False)
