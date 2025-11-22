"""Changed updated_at field in Jurisdiction from nullable to server_default and onupdate

Revision ID: 916a8a7a1889
Revises: 3e7e5f7ae4aa
Create Date: 2025-11-22 12:28:51.550468

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '916a8a7a1889'
down_revision: Union[str, Sequence[str], None] = '3e7e5f7ae4aa'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Set a server default for `updated_at` so new rows get the current
    # timestamp at insert time. We don't add a DB-side ON UPDATE trigger
    # here because the application (SQLAlchemy) supplies onupdate behavior
    # via the model's `onupdate=func.now()` configuration. If you want DB
    # side automatic update on every UPDATE, create a trigger (example
    # commented below).
    op.alter_column(
        "jurisdictions",
        "updated_at",
        existing_type=sa.DateTime(timezone=True),
        server_default=sa.text("NOW()"),
        existing_nullable=True,
    )

    # Example trigger (optional) to enforce DB-side updated_at updates:
    # NOTE: Uncomment and adjust if you want a DB trigger. Be careful if
    # your database already has a function/trigger with the same name.
    #
    # op.execute(
    #     """
    #     CREATE OR REPLACE FUNCTION update_updated_at_column()
    #     RETURNS TRIGGER AS $$
    #     BEGIN
    #         NEW.updated_at = NOW();
    #         RETURN NEW;
    #     END;
    #     $$ LANGUAGE plpgsql;
    #     """
    # )
    # op.execute(
    #     "CREATE TRIGGER trg_update_jurisdictions_updated_at BEFORE UPDATE ON jurisdictions FOR EACH ROW EXECUTE PROCEDURE update_updated_at_column();"
    # )


def downgrade() -> None:
    """Downgrade schema."""
    # Revert the server default we added for updated_at.
    op.alter_column(
        "jurisdictions",
        "updated_at",
        existing_type=sa.DateTime(timezone=True),
        server_default=None,
        existing_nullable=True,
    )

    # If you added the optional trigger in upgrade, drop it here (example):
    # op.execute("DROP TRIGGER IF EXISTS trg_update_jurisdictions_updated_at ON jurisdictions;")
    # op.execute("DROP FUNCTION IF EXISTS update_updated_at_column();")
