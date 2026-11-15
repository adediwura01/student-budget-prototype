"""Actual income/expense records, including their retained soft-deleted state."""

import sqlalchemy as sa

from ..extensions import db


class Transaction(db.Model):
    __tablename__ = "transactions"

    id = sa.Column(
        sa.Uuid(as_uuid=True), primary_key=True, nullable=False,
        server_default=sa.text("gen_random_uuid()"),
    )
    user_id = sa.Column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("users.id", name="fk_transactions_user", ondelete="RESTRICT",
                      onupdate="RESTRICT", deferrable=False, match="SIMPLE"),
        nullable=False,
    )
    transaction_type = sa.Column(sa.String(7), nullable=False)
    amount_kobo = sa.Column(sa.BigInteger, nullable=False)
    transaction_date = sa.Column(sa.Date, nullable=False)
    category_id = sa.Column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("categories.id", name="fk_transactions_category", ondelete="RESTRICT",
                      onupdate="RESTRICT", deferrable=False, match="SIMPLE"),
        nullable=True,
    )
    source = sa.Column(sa.String(120), nullable=True)
    description = sa.Column(sa.String(1000), nullable=True)
    plan_id = sa.Column(sa.Uuid(as_uuid=True), nullable=True)
    version = sa.Column(sa.Integer, nullable=False, server_default=sa.text("1"))
    deleted_at = sa.Column(sa.DateTime(timezone=True), nullable=True)
    recoverable_until = sa.Column(sa.DateTime(timezone=True), nullable=True)
    created_at = sa.Column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"),
    )
    updated_at = sa.Column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"),
    )

    __table_args__ = (
        sa.PrimaryKeyConstraint("id", name="pk_transactions", deferrable=False),
        sa.ForeignKeyConstraint(
            ["user_id", "plan_id", "transaction_type"], ["plans.user_id", "plans.id", "plans.plan_type"],
            name="fk_transactions_owned_plan_type", ondelete="RESTRICT", onupdate="RESTRICT", deferrable=False, match="SIMPLE",
        ),
        sa.UniqueConstraint("plan_id", name="uq_transactions_plan_id", deferrable=False),
        sa.CheckConstraint("transaction_type IN ('income', 'expense')", name="ck_transactions_type"),
        sa.CheckConstraint("amount_kobo >= 1", name="ck_transactions_amount_positive"),
        sa.CheckConstraint("isfinite(transaction_date)", name="ck_transactions_date_finite"),
        sa.CheckConstraint(
            "transaction_type <> 'expense' OR category_id IS NOT NULL",
            name="ck_transactions_expense_category",
        ),
        sa.CheckConstraint(
            "transaction_type <> 'income' OR (source IS NOT NULL AND char_length(btrim(source)) > 0)",
            name="ck_transactions_income_source",
        ),
        sa.CheckConstraint("version >= 1", name="ck_transactions_version_positive"),
        sa.CheckConstraint(
            "deleted_at IS NULL OR isfinite(deleted_at)", name="ck_transactions_deleted_at_finite",
        ),
        sa.CheckConstraint(
            "recoverable_until IS NULL OR isfinite(recoverable_until)",
            name="ck_transactions_recoverable_until_finite",
        ),
        sa.CheckConstraint(
            "(deleted_at IS NULL AND recoverable_until IS NULL) OR "
            "(deleted_at IS NOT NULL AND recoverable_until IS NOT NULL "
            "AND deleted_at >= created_at AND recoverable_until > deleted_at)",
            name="ck_transactions_recovery_state",
        ),
        sa.CheckConstraint("isfinite(created_at)", name="ck_transactions_created_at_finite"),
        sa.CheckConstraint("isfinite(updated_at)", name="ck_transactions_updated_at_finite"),
        sa.CheckConstraint("updated_at >= created_at", name="ck_transactions_update_order"),
        sa.Index(
            "ix_transactions_user_date_active", user_id, transaction_date.desc(), id,
            postgresql_where=deleted_at.is_(None),
        ),
        sa.Index(
            "ix_transactions_user_category_date_active", user_id, category_id, transaction_date.desc(), id,
            postgresql_where=deleted_at.is_(None),
        ),
        sa.Index(
            "ix_transactions_user_deleted", user_id, deleted_at.desc(), id,
            postgresql_where=deleted_at.is_not(None),
        ),
        sa.Index(
            "ix_transactions_recovery_deadline", recoverable_until, id,
            postgresql_where=deleted_at.is_not(None),
        ),
    )

    user = db.relationship(
        "User", back_populates="transactions", foreign_keys=[user_id], viewonly=True, cascade="",
    )
    category = db.relationship(
        "Category", back_populates="transactions", foreign_keys=[category_id],
        viewonly=True, cascade="",
    )
    plan = db.relationship(
        "Plan", back_populates="transaction", uselist=False, viewonly=True, cascade="",
        primaryjoin=(
            "and_(Transaction.user_id == Plan.user_id, Transaction.plan_id == Plan.id, "
            "Transaction.transaction_type == Plan.plan_type)"
        ),
        foreign_keys=[user_id, plan_id, transaction_type],
    )
