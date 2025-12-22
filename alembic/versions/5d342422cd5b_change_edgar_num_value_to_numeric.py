"""change edgar_num value to numeric

Revision ID: 5d342422cd5b
Revises: 2baee0a6feac
Create Date: 2025-12-16 22:06:35.226742

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5d342422cd5b'
down_revision: Union[str, None] = '2baee0a6feac'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Change value column from Float to Numeric(28, 4) for better precision with large financial values
    op.alter_column('edgar_num', 'value',
               existing_type=sa.DOUBLE_PRECISION(precision=53),
               type_=sa.Numeric(precision=28, scale=4),
               existing_nullable=True)


def downgrade() -> None:
    """Downgrade schema."""
    # Revert back to Float (double precision)
    op.alter_column('edgar_num', 'value',
               existing_type=sa.Numeric(precision=28, scale=4),
               type_=sa.DOUBLE_PRECISION(precision=53),
               existing_nullable=True)
