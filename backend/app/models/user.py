"""Account identity, preferences, and credential metadata."""

import sqlalchemy as sa

from ..extensions import db


class User(db.Model):
    __tablename__ = "users"

    id = sa.Column(
        sa.Uuid(as_uuid=True), primary_key=True, nullable=False,
        server_default=sa.text("gen_random_uuid()"),
    )
    full_name = sa.Column(sa.String(120), nullable=False)
    email = sa.Column(sa.String(254), nullable=False)
    password_hash = sa.Column(sa.Text, nullable=False)
    email_verified_at = sa.Column(sa.DateTime(timezone=True), nullable=True)
    credential_version = sa.Column(sa.Integer, nullable=False, server_default=sa.text("1"))
    appearance = sa.Column(sa.String(6), nullable=False, server_default=sa.text("'system'"))
    currency = sa.Column(sa.CHAR(3), nullable=False, server_default=sa.text("'NGN'"))
    date_format = sa.Column(sa.String(10), nullable=False, server_default=sa.text("'DD/MM/YYYY'"))
    week_start_day = sa.Column(sa.SmallInteger, nullable=False, server_default=sa.text("1"))
    last_successful_login_at = sa.Column(sa.DateTime(timezone=True), nullable=True)
    created_at = sa.Column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"),
    )
    updated_at = sa.Column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"),
    )

    __table_args__ = (
        sa.PrimaryKeyConstraint("id", name="pk_users", deferrable=False),
        sa.UniqueConstraint("email", name="uq_users_email", deferrable=False),
        sa.CheckConstraint("char_length(btrim(full_name)) > 0", name="ck_users_full_name_nonempty"),
        sa.CheckConstraint(
            "email = lower(btrim(email)) AND char_length(email) > 0",
            name="ck_users_email_normalized",
        ),
        sa.CheckConstraint("char_length(password_hash) BETWEEN 1 AND 1024", name="ck_users_password_hash_length"),
        sa.CheckConstraint("credential_version >= 1", name="ck_users_credential_version_positive"),
        sa.CheckConstraint("appearance IN ('light', 'dark', 'system')", name="ck_users_appearance"),
        sa.CheckConstraint("currency = 'NGN'", name="ck_users_currency"),
        sa.CheckConstraint(
            "date_format IN ('DD/MM/YYYY', 'MM/DD/YYYY', 'YYYY-MM-DD')",
            name="ck_users_date_format",
        ),
        sa.CheckConstraint("week_start_day IN (1, 7)", name="ck_users_week_start_day"),
        sa.CheckConstraint(
            "email_verified_at IS NULL OR isfinite(email_verified_at)",
            name="ck_users_email_verified_at_finite",
        ),
        sa.CheckConstraint(
            "email_verified_at IS NULL OR email_verified_at >= created_at",
            name="ck_users_verification_order",
        ),
        sa.CheckConstraint(
            "last_successful_login_at IS NULL OR isfinite(last_successful_login_at)",
            name="ck_users_last_login_finite",
        ),
        sa.CheckConstraint("isfinite(created_at)", name="ck_users_created_at_finite"),
        sa.CheckConstraint("isfinite(updated_at)", name="ck_users_updated_at_finite"),
        sa.CheckConstraint("updated_at >= created_at", name="ck_users_update_order"),
    )

    categories = db.relationship(
        "Category", back_populates="owner", foreign_keys="Category.owner_user_id",
        viewonly=True, cascade="",
    )
    transactions = db.relationship(
        "Transaction", back_populates="user", foreign_keys="Transaction.user_id",
        viewonly=True, cascade="",
    )
    plans = db.relationship(
        "Plan", back_populates="user", foreign_keys="Plan.user_id", viewonly=True, cascade="",
    )
    monthly_budgets = db.relationship(
        "MonthlyBudget", back_populates="user", foreign_keys="MonthlyBudget.user_id",
        viewonly=True, cascade="",
    )
    budget_limits = db.relationship(
        "BudgetLimit", back_populates="user", foreign_keys="BudgetLimit.user_id",
        viewonly=True, cascade="",
    )
    budget_alerts = db.relationship(
        "BudgetAlert", back_populates="user", foreign_keys="BudgetAlert.user_id",
        viewonly=True, cascade="",
    )
    login_sessions = db.relationship(
        "LoginSession", back_populates="user", foreign_keys="LoginSession.user_id",
        viewonly=True, cascade="",
    )
    auth_tokens = db.relationship(
        "AuthToken", back_populates="user", foreign_keys="AuthToken.user_id",
        viewonly=True, cascade="",
    )
