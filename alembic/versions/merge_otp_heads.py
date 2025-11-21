"""Merge OTP heads"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "merge_otp_heads"
down_revision = ["243540ac6fd8", "6c1547d1ae75"]
branch_labels = None
depends_on = None

def upgrade():
    """Nothing to do; just merging heads."""
    pass

def downgrade():
    """Nothing to do for downgrade."""
    pass

