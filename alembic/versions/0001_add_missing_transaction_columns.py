"""add missing transaction columns

Revision ID: 0001_add_missing_cols
Revises:
Create Date: 2026-06-27

Adds the 8 columns that were in the SQLAlchemy model but never reached Railway
because create_all() skips tables that already exist:
  reference_id, recipient_or_payer, notes, is_recurring, recurring_interval,
  tax_deductible, is_deleted, deleted_at
"""

from alembic import op
import sqlalchemy as sa

revision = "0001_add_missing_cols"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    # RecurringInterval is a new PG enum type — create it before the column.
    recurring_enum = sa.Enum(
        "daily", "weekly", "monthly", "quarterly", "annually",
        name="recurringinterval",
    )
    recurring_enum.create(bind, checkfirst=True)

    op.add_column("transactions",
        sa.Column("reference_id", sa.String(100), nullable=True))
    op.add_column("transactions",
        sa.Column("recipient_or_payer", sa.String(255), nullable=True))
    op.add_column("transactions",
        sa.Column("notes", sa.Text(), nullable=True))

    # NOT NULL with default — use server_default so existing rows get a value.
    op.add_column("transactions",
        sa.Column("is_recurring", sa.Boolean(), nullable=False,
                  server_default=sa.text("false")))
    op.add_column("transactions",
        sa.Column("recurring_interval",
                  sa.Enum("daily", "weekly", "monthly", "quarterly", "annually",
                          name="recurringinterval", create_type=False),
                  nullable=True))
    op.add_column("transactions",
        sa.Column("tax_deductible", sa.Boolean(), nullable=False,
                  server_default=sa.text("false")))
    op.add_column("transactions",
        sa.Column("is_deleted", sa.Boolean(), nullable=False,
                  server_default=sa.text("false")))
    op.add_column("transactions",
        sa.Column("deleted_at", sa.DateTime(), nullable=True))

    # Composite indexes defined in the model's __table_args__.
    # checkfirst guards against the rare case create_all() already made them.
    op.create_index("ix_txn_user_date",     "transactions", ["user_id", "transaction_date"], unique=False)
    op.create_index("ix_txn_user_type",     "transactions", ["user_id", "type"],             unique=False)
    op.create_index("ix_txn_user_category", "transactions", ["user_id", "category"],         unique=False)
    op.create_index("ix_transactions_is_deleted", "transactions", ["is_deleted"],             unique=False)


def downgrade() -> None:
    op.drop_index("ix_transactions_is_deleted", table_name="transactions")
    op.drop_index("ix_txn_user_category",       table_name="transactions")
    op.drop_index("ix_txn_user_type",           table_name="transactions")
    op.drop_index("ix_txn_user_date",           table_name="transactions")

    op.drop_column("transactions", "deleted_at")
    op.drop_column("transactions", "is_deleted")
    op.drop_column("transactions", "tax_deductible")
    op.drop_column("transactions", "recurring_interval")
    op.drop_column("transactions", "is_recurring")
    op.drop_column("transactions", "notes")
    op.drop_column("transactions", "recipient_or_payer")
    op.drop_column("transactions", "reference_id")

    sa.Enum(name="recurringinterval").drop(op.get_bind(), checkfirst=True)
