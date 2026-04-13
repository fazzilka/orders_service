from alembic import op

revision = "0002_optimize_orders_indexes"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("ix_orders_created_at", table_name="orders")
    op.drop_index("ix_orders_user_id", table_name="orders")
    op.create_index(
        "ix_orders_user_id_created_at",
        "orders",
        ["user_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_orders_user_id_created_at", table_name="orders")
    op.create_index("ix_orders_user_id", "orders", ["user_id"], unique=False)
    op.create_index("ix_orders_created_at", "orders", ["created_at"], unique=False)
