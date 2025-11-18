"""Increase varchar field sizes for robustness

Revision ID: b5a88b4fe6a7
Revises: b2a01e0082ff
Create Date: 2025-11-17 12:12:16.908812

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b5a88b4fe6a7'
down_revision: Union[str, None] = 'b2a01e0082ff'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - increase VARCHAR sizes for robustness."""
    # Increase field sizes in filings table to handle edge cases
    op.alter_column('filings', 'countryba', type_=sa.String(5), existing_type=sa.String(2))
    op.alter_column('filings', 'stprba', type_=sa.String(5), existing_type=sa.String(2))
    op.alter_column('filings', 'fiscal_period', type_=sa.String(20), existing_type=sa.String(10))


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column('filings', 'countryba', type_=sa.String(2), existing_type=sa.String(5))
    op.alter_column('filings', 'stprba', type_=sa.String(2), existing_type=sa.String(5))
    op.alter_column('filings', 'fiscal_period', type_=sa.String(10), existing_type=sa.String(20))
