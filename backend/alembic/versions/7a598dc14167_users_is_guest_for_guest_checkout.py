"""users.is_guest for guest checkout

Revision ID: 7a598dc14167
Revises: 97f0d135def1
Create Date: 2026-06-18 01:29:36.509983

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7a598dc14167'
down_revision: Union[str, Sequence[str], None] = '97f0d135def1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Plain ADD COLUMN with a server_default so existing rows backfill to False.
    # (The variant_id FKs Alembic also detected are intentionally app-enforced,
    # not DB-enforced, so they are not added here.)
    op.add_column('users', sa.Column('is_guest', sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('users', 'is_guest')
