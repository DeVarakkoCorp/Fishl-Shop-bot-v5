"""Baseline migration (идемпотентная для старых БД).

Revision ID: 0001_baseline
Revises:
Create Date: 2026-10-06
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0001_baseline"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    # 1. Таблица orders
    if "orders" not in existing_tables:
        op.create_table(
            "orders",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("created_at", sa.String(), nullable=False),
            sa.Column("client_telegram_id", sa.Integer(), nullable=False, index=True),
            sa.Column("client_name", sa.String(), nullable=False),
            sa.Column("uid", sa.String(), nullable=False),
            sa.Column("server", sa.String(), nullable=False),
            sa.Column("region", sa.String(), nullable=False),
            sa.Column("tier", sa.String(), nullable=False),
            sa.Column("price", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(), nullable=False, server_default="new"),
            sa.Column("manager_name", sa.String(), nullable=True, server_default=""),
            sa.Column("service", sa.String(), nullable=True, server_default=""),
            sa.Column("details", sa.String(), nullable=True, server_default=""),
            sa.Column("original_price", sa.Float(), nullable=True),
            sa.Column("discount_amount", sa.Float(), nullable=True, server_default="0"),
            sa.Column("discount_mode", sa.String(), nullable=True, server_default=""),
        )
    else:
        existing_cols = {col["name"] for col in inspector.get_columns("orders")}
        if "service" not in existing_cols:
            op.add_column("orders", sa.Column("service", sa.String(), server_default="", nullable=True))
        if "details" not in existing_cols:
            op.add_column("orders", sa.Column("details", sa.String(), server_default="", nullable=True))
        if "original_price" not in existing_cols:
            op.add_column("orders", sa.Column("original_price", sa.Float(), nullable=True))
        if "discount_amount" not in existing_cols:
            op.add_column("orders", sa.Column("discount_amount", sa.Float(), server_default="0", nullable=True))
        if "discount_mode" not in existing_cols:
            op.add_column("orders", sa.Column("discount_mode", sa.String(), server_default="", nullable=True))

    # 2. Таблица discounts
    if "discounts" not in existing_tables:
        op.create_table(
            "discounts",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("kind", sa.String(), nullable=False),
            sa.Column("threshold", sa.Float(), nullable=True, server_default="0"),
            sa.Column("service", sa.String(), nullable=True, server_default=""),
            sa.Column("percent", sa.Float(), nullable=False),
            sa.Column("value_type", sa.String(), nullable=False, server_default="%"),
            sa.Column("active", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("created_at", sa.String(), nullable=False),
            sa.Column("expires_at", sa.String(), nullable=True),
        )
    else:
        dcols = {col["name"] for col in inspector.get_columns("discounts")}
        if "value_type" not in dcols:
            op.add_column("discounts", sa.Column("value_type", sa.String(), server_default="%", nullable=False))
        if "expires_at" not in dcols:
            op.add_column("discounts", sa.Column("expires_at", sa.String(), nullable=True))

    # 3. Таблица service_categories
    if "service_categories" not in existing_tables:
        op.create_table(
            "service_categories",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("name", sa.String(), nullable=False, unique=True),
            sa.Column("active", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        )

    # 4. Таблица service_items
    if "service_items" not in existing_tables:
        op.create_table(
            "service_items",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("category_id", sa.Integer(), sa.ForeignKey("service_categories.id"), nullable=False),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("price", sa.Float(), nullable=False, server_default="0"),
            sa.Column("quantity_mode", sa.String(), nullable=False, server_default="fixed"),
            sa.Column("unit", sa.String(), nullable=False, server_default="шт."),
            sa.Column("active", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        )

    # 5. Таблица region_price_overrides
    if "region_price_overrides" not in existing_tables:
        op.create_table(
            "region_price_overrides",
            sa.Column("region", sa.String(), primary_key=True),
            sa.Column("price_0_100", sa.Float(), nullable=False),
            sa.Column("price_50_100", sa.Float(), nullable=False),
            sa.Column("price_80_100", sa.Float(), nullable=False),
        )

    # 6. Таблица fsm_state
    if "fsm_state" not in existing_tables:
        op.create_table(
            "fsm_state",
            sa.Column("key", sa.String(), primary_key=True),
            sa.Column("state", sa.String(), nullable=True),
            sa.Column("data", sa.Text(), nullable=False, server_default="{}"),
        )

    # 7. Таблица banners
    if "banners" not in existing_tables:
        op.create_table(
            "banners",
            sa.Column("key", sa.String(), primary_key=True),
            sa.Column("file_id", sa.String(), nullable=False),
            sa.Column("updated_at", sa.String(), nullable=False),
        )


def downgrade() -> None:
    op.drop_table("banners")
    op.drop_table("fsm_state")
    op.drop_table("region_price_overrides")
    op.drop_table("service_items")
    op.drop_table("service_categories")
    op.drop_table("discounts")
    op.drop_table("orders")
