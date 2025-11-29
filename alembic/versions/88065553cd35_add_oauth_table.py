"""add oauth_table

Revision ID: 88065553cd35
Revises: 84a91f4f3ead
Create Date: 2025-11-29 10:23:59.708519

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '88065553cd35'
down_revision: Union[str, Sequence[str], None] = '84a91f4f3ead'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Ensure ENUM type exists
    op.execute("""
        DO $$ BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_type WHERE typname = 'subscriptionplan'
            ) THEN
                CREATE TYPE subscriptionplan AS ENUM ('MONTHLY', 'YEARLY');
            END IF;
        END $$;
    """)

    # Create billing_subscriptions table
    op.create_table(
    'billing_subscriptions',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('billing_account_id', sa.Uuid(), nullable=False),
    sa.Column('stripe_subscription_id', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
    sa.Column('stripe_price_id', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True),
    sa.Column('plan', sa.Enum(name='subscriptionplan'), nullable=False),  # use existing ENUM
    sa.Column('status', sa.Enum('INCOMPLETE', 'INCOMPLETE_EXPIRED', 'TRIALING', 'ACTIVE', 'PAST_DUE', 'CANCELED', 'UNPAID', 'PAUSED', name='subscriptionstatus'), nullable=False),
    sa.Column('current_period_start', sa.DateTime(timezone=True), nullable=False),
    sa.Column('current_period_end', sa.DateTime(timezone=True), nullable=False),
    sa.Column('cancel_at_period_end', sa.Boolean(), nullable=False),
    sa.Column('canceled_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('ended_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('trial_start', sa.DateTime(timezone=True), nullable=True),
    sa.Column('trial_end', sa.DateTime(timezone=True), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('metadata', sa.JSON(), server_default='{}', nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['billing_account_id'], ['billing_accounts.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_billing_subscriptions_billing_account_id'), 'billing_subscriptions', ['billing_account_id'], unique=False)
    op.create_index(op.f('ix_billing_subscriptions_id'), 'billing_subscriptions', ['id'], unique=False)
    op.create_index(op.f('ix_billing_subscriptions_stripe_subscription_id'), 'billing_subscriptions', ['stripe_subscription_id'], unique=True)
    op.create_table('oauth_login_events',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=True),
    sa.Column('provider', sqlmodel.sql.sqltypes.AutoString(length=50), nullable=False),
    sa.Column('status', sqlmodel.sql.sqltypes.AutoString(length=20), nullable=False),
    sa.Column('failure_reason', sqlmodel.sql.sqltypes.AutoString(length=500), nullable=True),
    sa.Column('error_code', sqlmodel.sql.sqltypes.AutoString(length=100), nullable=True),
    sa.Column('ip_address', sqlmodel.sql.sqltypes.AutoString(length=45), nullable=True),
    sa.Column('user_agent', sqlmodel.sql.sqltypes.AutoString(length=500), nullable=True),
    sa.Column('email', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True),
    sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_oauth_login_events_email'), 'oauth_login_events', ['email'], unique=False)
    op.create_index(op.f('ix_oauth_login_events_id'), 'oauth_login_events', ['id'], unique=False)
    op.create_index(op.f('ix_oauth_login_events_timestamp'), 'oauth_login_events', ['timestamp'], unique=False)
    op.create_index(op.f('ix_oauth_login_events_user_id'), 'oauth_login_events', ['user_id'], unique=False)
    op.create_table('refresh_token_metadata',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('jti', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('provider', sqlmodel.sql.sqltypes.AutoString(length=50), nullable=False),
    sa.Column('provider_token_exp', sa.Integer(), nullable=True),
    sa.Column('issued_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('ip_address', sqlmodel.sql.sqltypes.AutoString(length=45), nullable=True),
    sa.Column('user_agent', sqlmodel.sql.sqltypes.AutoString(length=500), nullable=True),
    sa.Column('is_revoked', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_refresh_token_metadata_id'), 'refresh_token_metadata', ['id'], unique=False)
    op.create_index(op.f('ix_refresh_token_metadata_jti'), 'refresh_token_metadata', ['jti'], unique=True)
    op.create_index(op.f('ix_refresh_token_metadata_user_id'), 'refresh_token_metadata', ['user_id'], unique=False)
    op.add_column('users', sa.Column('profile_picture_url', sqlmodel.sql.sqltypes.AutoString(length=500), nullable=True))
    op.add_column('users', sa.Column('provider_profile_data', sa.JSON(), nullable=True))
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('users', 'provider_profile_data')
    op.drop_column('users', 'profile_picture_url')
    op.drop_index(op.f('ix_refresh_token_metadata_user_id'), table_name='refresh_token_metadata')
    op.drop_index(op.f('ix_refresh_token_metadata_jti'), table_name='refresh_token_metadata')
    op.drop_index(op.f('ix_refresh_token_metadata_id'), table_name='refresh_token_metadata')
    op.drop_table('refresh_token_metadata')
    op.drop_index(op.f('ix_oauth_login_events_user_id'), table_name='oauth_login_events')
    op.drop_index(op.f('ix_oauth_login_events_timestamp'), table_name='oauth_login_events')
    op.drop_index(op.f('ix_oauth_login_events_id'), table_name='oauth_login_events')
    op.drop_index(op.f('ix_oauth_login_events_email'), table_name='oauth_login_events')
    op.drop_table('oauth_login_events')
    op.drop_index(op.f('ix_billing_subscriptions_stripe_subscription_id'), table_name='billing_subscriptions')
    op.drop_index(op.f('ix_billing_subscriptions_id'), table_name='billing_subscriptions')
    op.drop_index(op.f('ix_billing_subscriptions_billing_account_id'), table_name='billing_subscriptions')
    op.drop_table('billing_subscriptions')
    # ### end Alembic commands ###
