"""运行上的节省回执。

Revision ID: 0003_savings_receipt
Revises: 0002_phase2
Create Date: 2026-11-24
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_savings_receipt"
down_revision: Union[str, None] = "0002_phase2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("runs", sa.Column("savings_receipt", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("runs", "savings_receipt")
