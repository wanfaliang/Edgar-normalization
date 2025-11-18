"""add_ticker_to_companies

Revision ID: 0a14c8d388fa
Revises: b5a88b4fe6a7
Create Date: 2025-11-17 17:00:28.252702

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0a14c8d388fa'
down_revision: Union[str, None] = 'b5a88b4fe6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - add ticker and exchange to companies table."""
    # Add ticker column
    op.add_column('companies', sa.Column('ticker', sa.String(10), nullable=True))

    # Add exchange column (NYSE, NASDAQ, etc.)
    op.add_column('companies', sa.Column('exchange', sa.String(10), nullable=True))

    # Create index on ticker for fast lookup
    op.create_index('ix_companies_ticker', 'companies', ['ticker'])


def downgrade() -> None:
    """Downgrade schema - remove ticker and exchange columns."""
    op.drop_index('ix_companies_ticker', 'companies')
    op.drop_column('companies', 'exchange')
    op.drop_column('companies', 'ticker')
