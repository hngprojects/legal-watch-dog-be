"""add organization_name to invitations table

Revision ID: c791d8ceca67
Revises: 2a965963ee24
Create Date: 2025-11-28 02:28:24.575774

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'c791d8ceca67'
down_revision: Union[str, Sequence[str], None] = '2a965963ee24'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    op.add_column('invitations', sa.Column('organization_name', sa.String(length=255), nullable=True))
    
    # Create index
    op.create_index(op.f('ix_invitations_organization_name'), 'invitations', ['organization_name'])
    
    op.execute("""
        UPDATE invitations 
        SET organization_name = organizations.name 
        FROM organizations 
        WHERE invitations.organization_id = organizations.id
    """)
    op.alter_column('invitations', 'organization_name', nullable=False)
  


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_invitations_organization_name'), table_name='invitations')
    op.drop_column('invitations', 'organization_name')
