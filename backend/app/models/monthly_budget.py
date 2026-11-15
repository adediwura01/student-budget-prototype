"""Primary monthly allocations; no stored spending or balance counters."""

import sqlalchemy as sa

from ..extensions import db


class MonthlyBudget(db.Model):
    __tablename__ = "monthly_budgets"

    id = sa.Column(
        sa.Uuid(as_uuid=True), primary_key=True, nullable=False,
        server_default=sa.text("gen_random_uuid()"),
    )
    user_id = sa.Column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("users.id", name="fk_monthly_budgets_user", ondelete="RESTRICT",
                      onupdate="RESTRICT", deferrable=False, match="SIMPLE"),
        nullable=False,
    )
    category_id = sa.Column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("categories.id", name="fk_monthly_budgets_category", ondelete="RESTRICT",
                      onupdate="RESTRICT", deferrable=False, match="SIMPLE"),
        nullable=False,
    )
    month_start = sa.Column(sa.Date, nullable=False)
    allocation_kobo = sa.Column(sa.BigInteger, nullable=False)
    warning_percent = sa.Column(sa.SmallInteger, nullable=False, server_default=sa.text("80"))
    archived_at = sa.Column(sa.DateTime(timezone=True), nullable=True)
    version = sa.Column(sa.Integer, nullable=False, server_default=sa.text("1"))
    created_at = sa.Column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"),
    )
    updated_at = sa.Column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"),
    )

    __table_args__ = (
        sa.PrimaryKeyConstraint("id", name="pk_monthly_budgets", deferrable=False),
        sa.UniqueConstraint(
            "user_id", "month_start", "category_id",
            name="uq_monthly_budgets_user_month_category", deferrable=False,
        ),
        sa.UniqueConstraint("user_id", "id", name="uq_monthly_budgets_user_id", deferrable=False),
        sa.CheckConstraint("isfinite(month_start)", name="ck_monthly_budgets_month_finite"),
        sa.CheckConstraint("EXTRACT(DAY FROM month_start) = 1", name="ck_monthly_budgets_month_start"),
        sa.CheckConstraint("allocation_kobo >= 1", name="ck_monthly_budgets_allocation_positive"),
        sa.CheckConstraint("warning_percent = 80", name="ck_monthly_budgets_warning_percent"),
        sa.CheckConstraint(
            "archived_at IS NULL OR isfinite(archived_at)",
            name="ck_monthly_budgets_archived_at_finite",
        ),
        sa.CheckConstraint("version >= 1", name="ck_monthly_budgets_version_positive"),
        sa.CheckConstraint("isfinite(created_at)", name="ck_monthly_budgets_created_at_finite"),
        sa.CheckConstraint("isfinite(updated_at)", name="ck_monthly_budgets_updated_at_finite"),
        sa.CheckConstraint("updated_at >= created_at", name="ck_monthly_budgets_update_order"),
    )

    user = db.relationship(
        "User", back_populates="monthly_budgets", foreign_keys=[user_id],
        viewonly=True, cascade="",
    )
    category = db.relationship(
        "Category", back_populates="monthly_budgets", foreign_keys=[category_id],
        viewonly=True, cascade="",
    )
    limits = db.relationship(
        "BudgetLimit", back_populates="budget", viewonly=True, cascade="",
        primaryjoin="and_(MonthlyBudget.user_id == BudgetLimit.user_id, MonthlyBudget.id == BudgetLimit.budget_id)",
        foreign_keys="[BudgetLimit.user_id, BudgetLimit.budget_id]",
    )
    alerts = db.relationship(
        "BudgetAlert", back_populates="budget", viewonly=True, cascade="",
        primaryjoin="and_(MonthlyBudget.user_id == BudgetAlert.user_id, MonthlyBudget.id == BudgetAlert.budget_id)",
        foreign_keys="[BudgetAlert.user_id, BudgetAlert.budget_id]",
    )
