"""Initial FinSet schema and PostgreSQL integrity/authorization guards.

Revision ID: 0001
Revises: None

This is a frozen schema snapshot, not an import of evolving application models.
The Alembic environment validates externally provisioned roles and assumes
finset_owner before any DDL. No role definitions or database data are seeded.
"""

from alembic import op
import sqlalchemy as sa


revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

TABLE_ORDER = (
    "users", "auth_tokens", "categories", "login_sessions", "monthly_budgets",
    "plans", "budget_limits", "transactions", "budget_alerts",
)

OWNER_ASSERTION = """
DO $finset_owner_check$
BEGIN
    IF current_user <> 'finset_owner' THEN
        RAISE EXCEPTION 'Use the role-checked Alembic environment and explicit finset_owner assumption'
            USING ERRCODE = '42501';
    END IF;
END;
$finset_owner_check$;
"""


def _create_tables():
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("full_name", sa.String(120), nullable=False),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("credential_version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("appearance", sa.String(6), server_default=sa.text("'system'"), nullable=False),
        sa.Column("currency", sa.CHAR(3), server_default=sa.text("'NGN'"), nullable=False),
        sa.Column("date_format", sa.String(10), server_default=sa.text("'DD/MM/YYYY'"), nullable=False),
        sa.Column("week_start_day", sa.SmallInteger(), server_default=sa.text("1"), nullable=False),
        sa.Column("last_successful_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("appearance IN ('light', 'dark', 'system')", name="ck_users_appearance"),
        sa.CheckConstraint("currency = 'NGN'", name="ck_users_currency"),
        sa.CheckConstraint("date_format IN ('DD/MM/YYYY', 'MM/DD/YYYY', 'YYYY-MM-DD')", name="ck_users_date_format"),
        sa.CheckConstraint("char_length(btrim(full_name)) > 0", name="ck_users_full_name_nonempty"),
        sa.CheckConstraint("char_length(password_hash) BETWEEN 1 AND 1024", name="ck_users_password_hash_length"),
        sa.CheckConstraint("credential_version >= 1", name="ck_users_credential_version_positive"),
        sa.CheckConstraint("email = lower(btrim(email)) AND char_length(email) > 0", name="ck_users_email_normalized"),
        sa.CheckConstraint("email_verified_at IS NULL OR email_verified_at >= created_at", name="ck_users_verification_order"),
        sa.CheckConstraint("email_verified_at IS NULL OR isfinite(email_verified_at)", name="ck_users_email_verified_at_finite"),
        sa.CheckConstraint("isfinite(created_at)", name="ck_users_created_at_finite"),
        sa.CheckConstraint("isfinite(updated_at)", name="ck_users_updated_at_finite"),
        sa.CheckConstraint("last_successful_login_at IS NULL OR isfinite(last_successful_login_at)", name="ck_users_last_login_finite"),
        sa.CheckConstraint("updated_at >= created_at", name="ck_users_update_order"),
        sa.CheckConstraint("week_start_day IN (1, 7)", name="ck_users_week_start_day"),
        sa.PrimaryKeyConstraint("id", name="pk_users", deferrable=False),
        sa.UniqueConstraint("email", name="uq_users_email", deferrable=False),
        schema="public",
    )
    op.create_table(
        "auth_tokens",
        sa.Column("id", sa.Uuid(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.LargeBinary(), nullable=False),
        sa.Column("purpose", sa.String(20), nullable=False),
        sa.Column("target_email", sa.String(254), nullable=True),
        sa.Column("credential_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "(purpose IN ('verify_email', 'change_email') AND target_email IS NOT NULL "
            "AND char_length(target_email) > 0 AND target_email = lower(btrim(target_email))) OR "
            "(purpose = 'reset_password' AND target_email IS NULL)", name="ck_auth_tokens_target_email",
        ),
        sa.CheckConstraint("purpose IN ('verify_email', 'reset_password', 'change_email')", name="ck_auth_tokens_purpose"),
        sa.CheckConstraint("consumed_at IS NULL OR consumed_at >= created_at", name="ck_auth_tokens_consumption_order"),
        sa.CheckConstraint("consumed_at IS NULL OR isfinite(consumed_at)", name="ck_auth_tokens_consumed_at_finite"),
        sa.CheckConstraint("consumed_at IS NULL OR revoked_at IS NULL", name="ck_auth_tokens_terminal_state"),
        sa.CheckConstraint("credential_version >= 1", name="ck_auth_tokens_credential_version"),
        sa.CheckConstraint("expires_at > created_at", name="ck_auth_tokens_expiry_order"),
        sa.CheckConstraint("isfinite(created_at)", name="ck_auth_tokens_created_at_finite"),
        sa.CheckConstraint("isfinite(expires_at)", name="ck_auth_tokens_expiry_finite"),
        sa.CheckConstraint("octet_length(token_hash) = 32", name="ck_auth_tokens_hash_length"),
        sa.CheckConstraint("revoked_at IS NULL OR isfinite(revoked_at)", name="ck_auth_tokens_revoked_at_finite"),
        sa.CheckConstraint("revoked_at IS NULL OR revoked_at >= created_at", name="ck_auth_tokens_revocation_order"),
        sa.ForeignKeyConstraint(["user_id"], ["public.users.id"], name="fk_auth_tokens_user", onupdate="RESTRICT", ondelete="CASCADE", match="SIMPLE", deferrable=False),
        sa.PrimaryKeyConstraint("id", name="pk_auth_tokens", deferrable=False),
        sa.UniqueConstraint("token_hash", name="uq_auth_tokens_token_hash", deferrable=False),
        schema="public",
    )
    op.create_table(
        "categories",
        sa.Column("id", sa.Uuid(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("category_type", sa.String(7), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("category_type IN ('income', 'expense')", name="ck_categories_type"),
        sa.CheckConstraint("archived_at IS NULL OR isfinite(archived_at)", name="ck_categories_archived_at_finite"),
        sa.CheckConstraint("char_length(btrim(name)) > 0", name="ck_categories_name_nonempty"),
        sa.CheckConstraint("isfinite(created_at)", name="ck_categories_created_at_finite"),
        sa.CheckConstraint("isfinite(updated_at)", name="ck_categories_updated_at_finite"),
        sa.CheckConstraint("updated_at >= created_at", name="ck_categories_update_order"),
        sa.ForeignKeyConstraint(["owner_user_id"], ["public.users.id"], name="fk_categories_owner", onupdate="RESTRICT", ondelete="RESTRICT", match="SIMPLE", deferrable=False),
        sa.PrimaryKeyConstraint("id", name="pk_categories", deferrable=False),
        schema="public",
    )
    op.create_table(
        "login_sessions",
        sa.Column("id", sa.Uuid(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.LargeBinary(), nullable=False),
        sa.Column("credential_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("last_activity_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("idle_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("credential_version >= 1", name="ck_login_sessions_credential_version"),
        sa.CheckConstraint("expires_at > created_at", name="ck_login_sessions_expiry_order"),
        sa.CheckConstraint("idle_expires_at > last_activity_at AND idle_expires_at <= expires_at", name="ck_login_sessions_idle_order"),
        sa.CheckConstraint("isfinite(created_at)", name="ck_login_sessions_created_at_finite"),
        sa.CheckConstraint("isfinite(expires_at)", name="ck_login_sessions_expiry_finite"),
        sa.CheckConstraint("isfinite(idle_expires_at)", name="ck_login_sessions_idle_expiry_finite"),
        sa.CheckConstraint("isfinite(last_activity_at)", name="ck_login_sessions_last_activity_finite"),
        sa.CheckConstraint("last_activity_at >= created_at", name="ck_login_sessions_activity_order"),
        sa.CheckConstraint("octet_length(token_hash) = 32", name="ck_login_sessions_hash_length"),
        sa.CheckConstraint("revoked_at IS NULL OR isfinite(revoked_at)", name="ck_login_sessions_revoked_at_finite"),
        sa.CheckConstraint("revoked_at IS NULL OR revoked_at >= created_at", name="ck_login_sessions_revocation_order"),
        sa.ForeignKeyConstraint(["user_id"], ["public.users.id"], name="fk_login_sessions_user", onupdate="RESTRICT", ondelete="CASCADE", match="SIMPLE", deferrable=False),
        sa.PrimaryKeyConstraint("id", name="pk_login_sessions", deferrable=False),
        sa.UniqueConstraint("token_hash", name="uq_login_sessions_token_hash", deferrable=False),
        schema="public",
    )
    op.create_table(
        "monthly_budgets",
        sa.Column("id", sa.Uuid(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("category_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("month_start", sa.Date(), nullable=False),
        sa.Column("allocation_kobo", sa.BigInteger(), nullable=False),
        sa.Column("warning_percent", sa.SmallInteger(), server_default=sa.text("80"), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("EXTRACT(DAY FROM month_start) = 1", name="ck_monthly_budgets_month_start"),
        sa.CheckConstraint("allocation_kobo >= 1", name="ck_monthly_budgets_allocation_positive"),
        sa.CheckConstraint("archived_at IS NULL OR isfinite(archived_at)", name="ck_monthly_budgets_archived_at_finite"),
        sa.CheckConstraint("isfinite(created_at)", name="ck_monthly_budgets_created_at_finite"),
        sa.CheckConstraint("isfinite(month_start)", name="ck_monthly_budgets_month_finite"),
        sa.CheckConstraint("isfinite(updated_at)", name="ck_monthly_budgets_updated_at_finite"),
        sa.CheckConstraint("updated_at >= created_at", name="ck_monthly_budgets_update_order"),
        sa.CheckConstraint("version >= 1", name="ck_monthly_budgets_version_positive"),
        sa.CheckConstraint("warning_percent = 80", name="ck_monthly_budgets_warning_percent"),
        sa.ForeignKeyConstraint(["category_id"], ["public.categories.id"], name="fk_monthly_budgets_category", onupdate="RESTRICT", ondelete="RESTRICT", match="SIMPLE", deferrable=False),
        sa.ForeignKeyConstraint(["user_id"], ["public.users.id"], name="fk_monthly_budgets_user", onupdate="RESTRICT", ondelete="RESTRICT", match="SIMPLE", deferrable=False),
        sa.PrimaryKeyConstraint("id", name="pk_monthly_budgets", deferrable=False),
        sa.UniqueConstraint("user_id", "id", name="uq_monthly_budgets_user_id", deferrable=False),
        sa.UniqueConstraint("user_id", "month_start", "category_id", name="uq_monthly_budgets_user_month_category", deferrable=False),
        schema="public",
    )
    op.create_table(
        "plans",
        sa.Column("id", sa.Uuid(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("plan_type", sa.String(7), nullable=False),
        sa.Column("expected_amount_kobo", sa.BigInteger(), nullable=False),
        sa.Column("expected_date", sa.Date(), nullable=False),
        sa.Column("category_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("source", sa.String(120), nullable=True),
        sa.Column("description", sa.String(1000), nullable=True),
        sa.Column("status", sa.String(9), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("result_generation", sa.SmallInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint(
            "(status = 'completed' AND completed_at IS NOT NULL AND completed_at >= created_at) OR "
            "(status IN ('pending', 'cancelled') AND completed_at IS NULL)", name="ck_plans_completion_state",
        ),
        sa.CheckConstraint("plan_type <> 'expense' OR category_id IS NOT NULL", name="ck_plans_expense_category"),
        sa.CheckConstraint("plan_type <> 'income' OR (source IS NOT NULL AND char_length(btrim(source)) > 0)", name="ck_plans_income_source"),
        sa.CheckConstraint("plan_type IN ('income', 'expense')", name="ck_plans_type"),
        sa.CheckConstraint("status IN ('pending', 'completed', 'cancelled')", name="ck_plans_status"),
        sa.CheckConstraint("completed_at IS NULL OR isfinite(completed_at)", name="ck_plans_completed_at_finite"),
        sa.CheckConstraint("expected_amount_kobo >= 1", name="ck_plans_expected_amount_positive"),
        sa.CheckConstraint("isfinite(created_at)", name="ck_plans_created_at_finite"),
        sa.CheckConstraint("isfinite(expected_date)", name="ck_plans_expected_date_finite"),
        sa.CheckConstraint("isfinite(updated_at)", name="ck_plans_updated_at_finite"),
        sa.CheckConstraint("result_generation BETWEEN 0 AND 2", name="ck_plans_result_generation_range"),
        sa.CheckConstraint("updated_at >= created_at", name="ck_plans_update_order"),
        sa.CheckConstraint("version >= 1", name="ck_plans_version_positive"),
        sa.ForeignKeyConstraint(["category_id"], ["public.categories.id"], name="fk_plans_category", onupdate="RESTRICT", ondelete="RESTRICT", match="SIMPLE", deferrable=False),
        sa.ForeignKeyConstraint(["user_id"], ["public.users.id"], name="fk_plans_user", onupdate="RESTRICT", ondelete="RESTRICT", match="SIMPLE", deferrable=False),
        sa.PrimaryKeyConstraint("id", name="pk_plans", deferrable=False),
        sa.UniqueConstraint("user_id", "id", "plan_type", name="uq_plans_user_id_type", deferrable=False),
        schema="public",
    )
    op.create_table(
        "budget_limits",
        sa.Column("id", sa.Uuid(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("budget_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("period_type", sa.String(6), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("week_start_day", sa.SmallInteger(), nullable=True),
        sa.Column("limit_kobo", sa.BigInteger(), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint(
            "(period_type = 'daily' AND week_start_day IS NULL AND end_date = start_date + 1) OR "
            "(period_type = 'weekly' AND week_start_day IS NOT NULL AND week_start_day IN (1, 7) "
            "AND end_date - start_date BETWEEN 1 AND 7 "
            "AND (EXTRACT(ISODOW FROM start_date) = week_start_day OR EXTRACT(DAY FROM start_date) = 1) "
            "AND (EXTRACT(ISODOW FROM end_date) = week_start_day OR EXTRACT(DAY FROM end_date) = 1))",
            name="ck_budget_limits_window_shape",
        ),
        sa.CheckConstraint("date_trunc('month', CAST(start_date AS timestamp)) = date_trunc('month', CAST(end_date - 1 AS timestamp))", name="ck_budget_limits_single_month"),
        sa.CheckConstraint("period_type IN ('daily', 'weekly')", name="ck_budget_limits_period_type"),
        sa.CheckConstraint("archived_at IS NULL OR isfinite(archived_at)", name="ck_budget_limits_archived_at_finite"),
        sa.CheckConstraint("end_date > start_date", name="ck_budget_limits_date_order"),
        sa.CheckConstraint("isfinite(created_at)", name="ck_budget_limits_created_at_finite"),
        sa.CheckConstraint("isfinite(end_date)", name="ck_budget_limits_end_date_finite"),
        sa.CheckConstraint("isfinite(start_date)", name="ck_budget_limits_start_date_finite"),
        sa.CheckConstraint("isfinite(updated_at)", name="ck_budget_limits_updated_at_finite"),
        sa.CheckConstraint("limit_kobo >= 1", name="ck_budget_limits_amount_positive"),
        sa.CheckConstraint("updated_at >= created_at", name="ck_budget_limits_update_order"),
        sa.CheckConstraint("version >= 1", name="ck_budget_limits_version_positive"),
        sa.ForeignKeyConstraint(["user_id", "budget_id"], ["public.monthly_budgets.user_id", "public.monthly_budgets.id"], name="fk_budget_limits_owned_budget", onupdate="RESTRICT", ondelete="RESTRICT", match="SIMPLE", deferrable=False),
        sa.ForeignKeyConstraint(["user_id"], ["public.users.id"], name="fk_budget_limits_user", onupdate="RESTRICT", ondelete="RESTRICT", match="SIMPLE", deferrable=False),
        sa.PrimaryKeyConstraint("id", name="pk_budget_limits", deferrable=False),
        sa.UniqueConstraint("user_id", "budget_id", "id", name="uq_budget_limits_user_budget_id", deferrable=False),
        schema="public",
    )
    op.create_table(
        "transactions",
        sa.Column("id", sa.Uuid(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("transaction_type", sa.String(7), nullable=False),
        sa.Column("amount_kobo", sa.BigInteger(), nullable=False),
        sa.Column("transaction_date", sa.Date(), nullable=False),
        sa.Column("category_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("source", sa.String(120), nullable=True),
        sa.Column("description", sa.String(1000), nullable=True),
        sa.Column("plan_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("recoverable_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("transaction_type <> 'expense' OR category_id IS NOT NULL", name="ck_transactions_expense_category"),
        sa.CheckConstraint("transaction_type <> 'income' OR (source IS NOT NULL AND char_length(btrim(source)) > 0)", name="ck_transactions_income_source"),
        sa.CheckConstraint("transaction_type IN ('income', 'expense')", name="ck_transactions_type"),
        sa.CheckConstraint(
            "(deleted_at IS NULL AND recoverable_until IS NULL) OR "
            "(deleted_at IS NOT NULL AND recoverable_until IS NOT NULL "
            "AND deleted_at >= created_at AND recoverable_until > deleted_at)", name="ck_transactions_recovery_state",
        ),
        sa.CheckConstraint("amount_kobo >= 1", name="ck_transactions_amount_positive"),
        sa.CheckConstraint("deleted_at IS NULL OR isfinite(deleted_at)", name="ck_transactions_deleted_at_finite"),
        sa.CheckConstraint("isfinite(created_at)", name="ck_transactions_created_at_finite"),
        sa.CheckConstraint("isfinite(transaction_date)", name="ck_transactions_date_finite"),
        sa.CheckConstraint("isfinite(updated_at)", name="ck_transactions_updated_at_finite"),
        sa.CheckConstraint("recoverable_until IS NULL OR isfinite(recoverable_until)", name="ck_transactions_recoverable_until_finite"),
        sa.CheckConstraint("updated_at >= created_at", name="ck_transactions_update_order"),
        sa.CheckConstraint("version >= 1", name="ck_transactions_version_positive"),
        sa.ForeignKeyConstraint(["category_id"], ["public.categories.id"], name="fk_transactions_category", onupdate="RESTRICT", ondelete="RESTRICT", match="SIMPLE", deferrable=False),
        sa.ForeignKeyConstraint(["user_id", "plan_id", "transaction_type"], ["public.plans.user_id", "public.plans.id", "public.plans.plan_type"], name="fk_transactions_owned_plan_type", onupdate="RESTRICT", ondelete="RESTRICT", match="SIMPLE", deferrable=False),
        sa.ForeignKeyConstraint(["user_id"], ["public.users.id"], name="fk_transactions_user", onupdate="RESTRICT", ondelete="RESTRICT", match="SIMPLE", deferrable=False),
        sa.PrimaryKeyConstraint("id", name="pk_transactions", deferrable=False),
        sa.UniqueConstraint("plan_id", name="uq_transactions_plan_id", deferrable=False),
        schema="public",
    )
    op.create_table(
        "budget_alerts",
        sa.Column("id", sa.Uuid(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("budget_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("budget_limit_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("alert_type", sa.String(11), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("threshold_percent", sa.SmallInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("(alert_type = 'warning' AND threshold_percent = 80) OR (alert_type = 'over_budget' AND threshold_percent = 100)", name="ck_budget_alerts_threshold"),
        sa.CheckConstraint("alert_type IN ('warning', 'over_budget')", name="ck_budget_alerts_type"),
        sa.CheckConstraint("isfinite(created_at)", name="ck_budget_alerts_created_at_finite"),
        sa.CheckConstraint("isfinite(period_end)", name="ck_budget_alerts_period_end_finite"),
        sa.CheckConstraint("isfinite(period_start)", name="ck_budget_alerts_period_start_finite"),
        sa.CheckConstraint("period_end > period_start", name="ck_budget_alerts_period_order"),
        sa.CheckConstraint("read_at IS NULL OR isfinite(read_at)", name="ck_budget_alerts_read_at_finite"),
        sa.CheckConstraint("read_at IS NULL OR read_at >= created_at", name="ck_budget_alerts_read_order"),
        sa.CheckConstraint("resolved_at IS NULL OR isfinite(resolved_at)", name="ck_budget_alerts_resolved_at_finite"),
        sa.CheckConstraint("resolved_at IS NULL OR resolved_at >= created_at", name="ck_budget_alerts_resolution_order"),
        sa.ForeignKeyConstraint(["user_id", "budget_id", "budget_limit_id"], ["public.budget_limits.user_id", "public.budget_limits.budget_id", "public.budget_limits.id"], name="fk_budget_alerts_owned_limit", onupdate="RESTRICT", ondelete="RESTRICT", match="SIMPLE", deferrable=False),
        sa.ForeignKeyConstraint(["user_id", "budget_id"], ["public.monthly_budgets.user_id", "public.monthly_budgets.id"], name="fk_budget_alerts_owned_budget", onupdate="RESTRICT", ondelete="RESTRICT", match="SIMPLE", deferrable=False),
        sa.ForeignKeyConstraint(["user_id"], ["public.users.id"], name="fk_budget_alerts_user", onupdate="RESTRICT", ondelete="RESTRICT", match="SIMPLE", deferrable=False),
        sa.PrimaryKeyConstraint("id", name="pk_budget_alerts", deferrable=False),
        schema="public",
    )


def _create_indexes():
    op.create_index("ix_auth_tokens_invalidation", "auth_tokens", [sa.literal_column("least(expires_at, consumed_at, revoked_at)")], schema="public")
    op.create_index("ix_auth_tokens_user", "auth_tokens", ["user_id"], schema="public")
    op.create_index("uq_auth_tokens_outstanding_purpose", "auth_tokens", ["user_id", "purpose"], unique=True, schema="public", postgresql_where=sa.text("consumed_at IS NULL AND revoked_at IS NULL"))
    op.create_index("uq_categories_custom_owner_name", "categories", ["owner_user_id", sa.literal_column("lower(btrim(name))")], unique=True, schema="public", postgresql_where=sa.text("owner_user_id IS NOT NULL"))
    op.create_index("uq_categories_system_name_type", "categories", [sa.literal_column("lower(btrim(name))"), "category_type"], unique=True, schema="public", postgresql_where=sa.text("owner_user_id IS NULL"))
    op.create_index("ix_login_sessions_invalidation", "login_sessions", [sa.literal_column("least(expires_at, idle_expires_at, revoked_at)")], schema="public")
    op.create_index("ix_login_sessions_user", "login_sessions", ["user_id"], schema="public")
    op.create_index("ix_plans_user_status_date", "plans", ["user_id", "status", "expected_date", "id"], schema="public")
    op.create_index("uq_budget_limits_active_start", "budget_limits", ["budget_id", "period_type", "start_date"], unique=True, schema="public", postgresql_where=sa.text("archived_at IS NULL"))
    op.create_index("ix_transactions_recovery_deadline", "transactions", ["recoverable_until", "id"], schema="public", postgresql_where=sa.text("deleted_at IS NOT NULL"))
    op.create_index("ix_transactions_user_category_date_active", "transactions", ["user_id", "category_id", sa.literal_column("transaction_date DESC"), "id"], schema="public", postgresql_where=sa.text("deleted_at IS NULL"))
    op.create_index("ix_transactions_user_date_active", "transactions", ["user_id", sa.literal_column("transaction_date DESC"), "id"], schema="public", postgresql_where=sa.text("deleted_at IS NULL"))
    op.create_index("ix_transactions_user_deleted", "transactions", ["user_id", sa.literal_column("deleted_at DESC"), "id"], schema="public", postgresql_where=sa.text("deleted_at IS NOT NULL"))
    op.create_index("ix_budget_alerts_user_created", "budget_alerts", ["user_id", sa.literal_column("created_at DESC"), "id"], schema="public")
    op.create_index("uq_budget_alerts_active_scope", "budget_alerts", ["budget_id", "budget_limit_id", "alert_type"], unique=True, schema="public", postgresql_where=sa.text("resolved_at IS NULL"), postgresql_nulls_not_distinct=True)


FUNCTIONS = {
    "finset_guard_immutable": ("INVOKER", """
DECLARE
    column_name text;
    old_values jsonb := pg_catalog.to_jsonb(OLD);
    new_values jsonb := pg_catalog.to_jsonb(NEW);
BEGIN
    IF TG_OP <> 'UPDATE' OR TG_TABLE_SCHEMA <> 'public' THEN
        RAISE EXCEPTION 'Invalid immutable-guard context' USING ERRCODE = '55000';
    END IF;
    FOREACH column_name IN ARRAY TG_ARGV LOOP
        IF NOT (old_values ? column_name) OR NOT (new_values ? column_name) THEN
            RAISE EXCEPTION 'Invalid immutable-guard column' USING ERRCODE = '55000';
        END IF;
        IF (old_values -> column_name) IS DISTINCT FROM (new_values -> column_name) THEN
            RAISE EXCEPTION USING ERRCODE = '23514',
                MESSAGE = 'Immutable field ' || TG_TABLE_NAME || '.' || column_name || ' cannot change';
        END IF;
    END LOOP;
    RETURN NEW;
END;
"""),
    "finset_guard_category_mutation": ("INVOKER", """
DECLARE
    row_owner uuid;
    maintenance_actor boolean := pg_catalog.pg_has_role(current_user, 'finset_maintenance', 'USAGE');
    runtime_actor boolean := pg_catalog.pg_has_role(current_user, 'finset_runtime', 'USAGE');
BEGIN
    IF TG_RELID <> CAST('public.categories' AS regclass) THEN
        RAISE EXCEPTION 'Invalid category-guard context' USING ERRCODE = '55000';
    END IF;
    IF TG_OP = 'DELETE' THEN
        row_owner := OLD.owner_user_id;
    ELSE
        row_owner := NEW.owner_user_id;
    END IF;
    IF row_owner IS NULL THEN
        IF NOT maintenance_actor OR runtime_actor
           OR pg_catalog.pg_has_role(current_user, 'finset_owner', 'USAGE')
           OR pg_catalog.pg_has_role(current_user, 'finset_migrator', 'USAGE') THEN
            RAISE EXCEPTION 'System-category writes require the maintenance identity'
                USING ERRCODE = '42501';
        END IF;
    ELSE
        IF NOT runtime_actor OR maintenance_actor
           OR pg_catalog.pg_has_role(current_user, 'finset_owner', 'MEMBER')
           OR pg_catalog.pg_has_role(current_user, 'finset_migrator', 'MEMBER') THEN
            RAISE EXCEPTION 'Private category operations require the isolated runtime identity'
                USING ERRCODE = '42501';
        END IF;
    END IF;
    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    RETURN NEW;
END;
"""),
    "finset_guard_category_reference": ("INVOKER", """
DECLARE
    category_owner uuid;
    category_kind text;
    category_archived_at timestamptz;
    expected_kind text;
    new_selection boolean;
BEGIN
    IF TG_TABLE_SCHEMA <> 'public' OR TG_OP NOT IN ('INSERT', 'UPDATE') THEN
        RAISE EXCEPTION 'Invalid category-reference context' USING ERRCODE = '55000';
    END IF;
    IF TG_TABLE_NAME = 'transactions' THEN
        expected_kind := NEW.transaction_type;
    ELSIF TG_TABLE_NAME = 'plans' THEN
        expected_kind := NEW.plan_type;
    ELSIF TG_TABLE_NAME = 'monthly_budgets' THEN
        expected_kind := 'expense';
    ELSE
        RAISE EXCEPTION 'Invalid category-reference table' USING ERRCODE = '55000';
    END IF;
    IF NEW.category_id IS NULL THEN
        -- The ordinary expense-category checks/NOT NULL constraint still apply.
        RETURN NEW;
    END IF;

    -- SHARE, not KEY SHARE, conflicts with a concurrent non-key archive update.
    SELECT c.owner_user_id, c.category_type, c.archived_at
    INTO category_owner, category_kind, category_archived_at
    FROM public.categories AS c WHERE c.id = NEW.category_id FOR SHARE OF c;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Referenced category does not exist' USING ERRCODE = '23503';
    END IF;
    IF category_owner IS NOT NULL AND category_owner IS DISTINCT FROM NEW.user_id THEN
        RAISE EXCEPTION 'Category is not available to this record owner' USING ERRCODE = '23514';
    END IF;
    IF category_kind IS DISTINCT FROM expected_kind THEN
        RAISE EXCEPTION 'Category type does not match the financial record' USING ERRCODE = '23514';
    END IF;
    IF TG_OP = 'INSERT' THEN
        new_selection := true;
    ELSE
        new_selection := NEW.category_id IS DISTINCT FROM OLD.category_id
                         OR NEW.user_id IS DISTINCT FROM OLD.user_id;
    END IF;
    IF new_selection AND category_archived_at IS NOT NULL THEN
        RAISE EXCEPTION 'Archived categories cannot be newly selected' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
"""),
    "finset_guard_lifecycle": ("INVOKER", """
BEGIN
    IF TG_OP <> 'UPDATE' OR TG_TABLE_SCHEMA <> 'public' THEN
        RAISE EXCEPTION 'Invalid lifecycle-guard context' USING ERRCODE = '55000';
    END IF;
    IF TG_TABLE_NAME = 'users' THEN
        IF NEW.credential_version < OLD.credential_version THEN
            RAISE EXCEPTION 'Credential version cannot decrease' USING ERRCODE = '23514';
        END IF;
    ELSIF TG_TABLE_NAME = 'login_sessions' THEN
        IF NEW.last_activity_at < OLD.last_activity_at OR NEW.idle_expires_at < OLD.idle_expires_at THEN
            RAISE EXCEPTION 'Session activity and idle deadline cannot decrease' USING ERRCODE = '23514';
        END IF;
        IF OLD.revoked_at IS NOT NULL AND NEW.revoked_at IS NULL THEN
            RAISE EXCEPTION 'A revoked session cannot be revived' USING ERRCODE = '23514';
        END IF;
    ELSIF TG_TABLE_NAME = 'auth_tokens' THEN
        IF (OLD.consumed_at IS NOT NULL AND NEW.consumed_at IS NULL)
           OR (OLD.revoked_at IS NOT NULL AND NEW.revoked_at IS NULL) THEN
            RAISE EXCEPTION 'Consumed or revoked credentials cannot be reopened' USING ERRCODE = '23514';
        END IF;
    ELSIF TG_TABLE_NAME = 'budget_alerts' THEN
        IF OLD.resolved_at IS NOT NULL AND NEW.resolved_at IS NULL THEN
            RAISE EXCEPTION 'Resolved alerts cannot be reopened' USING ERRCODE = '23514';
        END IF;
    ELSIF TG_TABLE_NAME = 'transactions' THEN
        IF OLD.deleted_at IS NOT NULL AND NEW.deleted_at IS NOT NULL
           AND (NEW.deleted_at IS DISTINCT FROM OLD.deleted_at
                OR NEW.recoverable_until IS DISTINCT FROM OLD.recoverable_until) THEN
            RAISE EXCEPTION 'An existing deletion recovery window cannot be reset' USING ERRCODE = '23514';
        END IF;
    ELSE
        RAISE EXCEPTION 'Invalid lifecycle-guard table' USING ERRCODE = '55000';
    END IF;
    RETURN NEW;
END;
"""),
    "finset_guard_plan_generation": ("INVOKER", """
BEGIN
    IF TG_RELID <> CAST('public.plans' AS regclass) THEN
        RAISE EXCEPTION 'Invalid generation-guard context' USING ERRCODE = '55000';
    END IF;
    IF TG_OP = 'INSERT' THEN
        IF NEW.result_generation IS DISTINCT FROM 0 THEN
            RAISE EXCEPTION 'New plans start with no allocated result' USING ERRCODE = '23514';
        END IF;
    ELSIF TG_OP = 'UPDATE' THEN
        IF NEW.result_generation IS DISTINCT FROM OLD.result_generation THEN
            -- The role is the authority; depth alone is never a maintenance flag.
            -- Runtime lacks column UPDATE and EXECUTE on the owner-only allocator.
            IF current_user <> 'finset_owner' OR pg_catalog.pg_trigger_depth() < 2
               OR NEW.result_generation IS NULL
               OR NEW.result_generation <> OLD.result_generation + 1
               OR OLD.result_generation NOT IN (0, 1)
               OR OLD.status <> 'pending' OR NEW.status <> 'pending' THEN
                RAISE EXCEPTION 'Result generation is controlled only by the protected insert allocator'
                    USING ERRCODE = '42501';
            END IF;
        END IF;
    ELSE
        RAISE EXCEPTION 'Invalid generation-guard operation' USING ERRCODE = '55000';
    END IF;
    RETURN NEW;
END;
"""),
    "finset_prepare_plan_result": ("INVOKER", """
DECLARE
    plan_status text;
    generation smallint;
BEGIN
    IF TG_OP <> 'INSERT' OR TG_RELID <> CAST('public.transactions' AS regclass) THEN
        RAISE EXCEPTION 'Invalid result-preparation context' USING ERRCODE = '55000';
    END IF;
    IF NEW.plan_id IS NULL THEN
        RETURN NEW;
    END IF;
    -- Services already hold the User -> Plan locks. This also serializes raw
    -- concurrent inserts for this plan without first locking an absent result.
    SELECT p.status, p.result_generation INTO plan_status, generation
    FROM public.plans AS p
    WHERE p.id = NEW.plan_id AND p.user_id = NEW.user_id AND p.plan_type = NEW.transaction_type
    FOR UPDATE OF p;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Result requires a matching owned plan and type' USING ERRCODE = '23503';
    END IF;
    IF plan_status <> 'pending' OR generation NOT IN (0, 1) THEN
        RAISE EXCEPTION 'Plan is not eligible for a new result allocation' USING ERRCODE = '23514';
    END IF;
    IF EXISTS (SELECT 1 FROM public.transactions WHERE plan_id = NEW.plan_id) THEN
        RAISE EXCEPTION 'A retained plan result must be reused, not duplicated' USING ERRCODE = '23505';
    END IF;
    RETURN NEW;
END;
"""),
    "finset_allocate_plan_result": ("DEFINER", """
DECLARE
    affected integer;
BEGIN
    IF TG_OP <> 'INSERT' OR TG_WHEN <> 'AFTER'
       OR TG_RELID <> CAST('public.transactions' AS regclass) THEN
        RAISE EXCEPTION 'Invalid result-allocation context' USING ERRCODE = '55000';
    END IF;
    IF NEW.plan_id IS NULL THEN
        RETURN NULL;
    END IF;
    -- AFTER INSERT is essential: skipped ON CONFLICT rows consume no generation.
    IF NOT EXISTS (
        SELECT 1 FROM public.transactions AS t
        WHERE t.id = NEW.id AND t.plan_id = NEW.plan_id
          AND t.user_id = NEW.user_id AND t.transaction_type = NEW.transaction_type
    ) THEN
        RAISE EXCEPTION 'A result must exist before allocation' USING ERRCODE = '23514';
    END IF;
    UPDATE public.plans
    SET result_generation = result_generation + 1
    WHERE id = NEW.plan_id AND user_id = NEW.user_id AND plan_type = NEW.transaction_type
      AND status = 'pending' AND result_generation IN (0, 1);
    GET DIAGNOSTICS affected = ROW_COUNT;
    IF affected <> 1 THEN
        RAISE EXCEPTION 'Plan result allocation is unavailable' USING ERRCODE = '23514';
    END IF;
    RETURN NULL;
END;
"""),
    "finset_check_plan_result": ("INVOKER", """
DECLARE
    plan_ids uuid[] := ARRAY[]::uuid[];
    target_id uuid;
    plan_status text;
    generation smallint;
    retained bigint;
    active_results bigint;
BEGIN
    IF TG_TABLE_SCHEMA <> 'public' THEN
        RAISE EXCEPTION 'Invalid plan-state context' USING ERRCODE = '55000';
    END IF;
    IF TG_TABLE_NAME = 'plans' THEN
        IF TG_OP <> 'INSERT' THEN plan_ids := pg_catalog.array_append(plan_ids, OLD.id); END IF;
        IF TG_OP <> 'DELETE' THEN plan_ids := pg_catalog.array_append(plan_ids, NEW.id); END IF;
    ELSIF TG_TABLE_NAME = 'transactions' THEN
        IF TG_OP <> 'INSERT' THEN plan_ids := pg_catalog.array_append(plan_ids, OLD.plan_id); END IF;
        IF TG_OP <> 'DELETE' THEN plan_ids := pg_catalog.array_append(plan_ids, NEW.plan_id); END IF;
    ELSE
        RAISE EXCEPTION 'Invalid plan-state table' USING ERRCODE = '55000';
    END IF;

    FOR target_id IN SELECT DISTINCT value FROM pg_catalog.unnest(plan_ids) AS ids(value)
                     WHERE value IS NOT NULL LOOP
        -- Read final rows, not queued NEW/status values or event-time WHEN tests.
        -- Never first acquire the User/Plan write locks from this deferred check.
        SELECT status, result_generation INTO plan_status, generation
        FROM public.plans WHERE id = target_id;
        IF NOT FOUND THEN
            IF EXISTS (SELECT 1 FROM public.transactions WHERE plan_id = target_id) THEN
                RAISE EXCEPTION 'A result cannot outlive its plan' USING ERRCODE = '23503';
            END IF;
            CONTINUE;
        END IF;
        SELECT count(*), count(*) FILTER (WHERE deleted_at IS NULL)
        INTO retained, active_results FROM public.transactions WHERE plan_id = target_id;
        IF retained > 1
           OR (plan_status = 'completed' AND active_results <> 1)
           OR (plan_status IN ('pending', 'cancelled') AND active_results <> 0)
           OR (generation = 0 AND retained <> 0)
           OR (retained > 0 AND generation NOT IN (1, 2)) THEN
            RAISE EXCEPTION 'Plan and actual-result final state disagree'
                USING ERRCODE = '23514', CONSTRAINT = 'finset_plan_result_final_state';
        END IF;
    END LOOP;
    RETURN NULL;
END;
"""),
}

# Fixed schema-owned trigger arguments are not caller-supplied authorization.
IMMUTABLE_COLUMNS = {
    "users": ("id", "created_at"),
    "categories": ("id", "owner_user_id", "category_type", "created_at"),
    "plans": ("id", "user_id", "plan_type", "created_at"),
    "transactions": ("id", "user_id", "plan_id", "created_at"),
    "monthly_budgets": ("id", "user_id", "category_id", "month_start", "created_at"),
    "budget_limits": ("id", "user_id", "budget_id", "period_type", "created_at"),
    "budget_alerts": ("id", "user_id", "budget_id", "budget_limit_id", "alert_type", "period_start", "period_end", "threshold_percent", "created_at"),
    "login_sessions": ("id", "user_id", "token_hash", "credential_version", "created_at", "expires_at"),
    "auth_tokens": ("id", "user_id", "token_hash", "purpose", "target_email", "credential_version", "created_at", "expires_at"),
}

TRIGGERS = [
    (table, "finset_10_immutable", f"BEFORE UPDATE ON public.{table} FOR EACH ROW "
     "EXECUTE FUNCTION public.finset_guard_immutable(" + ", ".join(f"'{column}'" for column in columns) + ")")
    for table, columns in IMMUTABLE_COLUMNS.items()
]
TRIGGERS += [
    ("categories", "finset_20_category_mutation", "BEFORE INSERT OR UPDATE OR DELETE ON public.categories FOR EACH ROW EXECUTE FUNCTION public.finset_guard_category_mutation()"),
    ("plans", "finset_20_plan_generation", "BEFORE INSERT OR UPDATE ON public.plans FOR EACH ROW EXECUTE FUNCTION public.finset_guard_plan_generation()"),
    ("transactions", "finset_00_prepare_plan_result", "BEFORE INSERT ON public.transactions FOR EACH ROW EXECUTE FUNCTION public.finset_prepare_plan_result()"),
    ("transactions", "finset_40_allocate_plan_result", "AFTER INSERT ON public.transactions FOR EACH ROW EXECUTE FUNCTION public.finset_allocate_plan_result()"),
]
TRIGGERS += [
    (table, "finset_30_category_reference", f"BEFORE INSERT OR UPDATE ON public.{table} FOR EACH ROW EXECUTE FUNCTION public.finset_guard_category_reference()")
    for table in ("transactions", "plans", "monthly_budgets")
]
TRIGGERS += [
    (table, "finset_30_lifecycle", f"BEFORE UPDATE ON public.{table} FOR EACH ROW EXECUTE FUNCTION public.finset_guard_lifecycle()")
    for table in ("users", "login_sessions", "auth_tokens", "budget_alerts", "transactions")
]
TRIGGERS += [
    (table, "finset_90_plan_result_consistency", f"AFTER INSERT OR UPDATE OR DELETE ON public.{table} "
     "DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION public.finset_check_plan_result()")
    for table in ("plans", "transactions")
]


def _install_enforcement():
    for name, (security_mode, body) in FUNCTIONS.items():
        # Application objects are explicitly qualified; never resolve them through
        # a schema that might be writable by an untrusted caller.
        op.execute(
            f"CREATE FUNCTION public.{name}() RETURNS trigger LANGUAGE plpgsql VOLATILE "
            f"SECURITY {security_mode} SET search_path = pg_catalog, pg_temp "
            f"AS $finset_body$\n{body}\n$finset_body$;"
        )
        op.execute(f"ALTER FUNCTION public.{name}() OWNER TO finset_owner")
        # Trigger creation is performed by the owner. Ordinary DML invokes the
        # installed trigger without making its privileged function a public API.
        op.execute(
            f"REVOKE ALL ON FUNCTION public.{name}() "
            "FROM PUBLIC, finset_runtime, finset_migrator, finset_maintenance"
        )
    for _, name, definition in TRIGGERS:
        kind = "CONSTRAINT TRIGGER" if name == "finset_90_plan_result_consistency" else "TRIGGER"
        op.execute(f"CREATE {kind} {name} {definition}")
    # Updatable owner-permission view; underlying invoker triggers still see the
    # actual maintenance caller, not the view owner. No private categories leak.
    op.execute("""
        CREATE VIEW public.finset_system_categories
        WITH (security_barrier = true, security_invoker = false) AS
        SELECT id, name, category_type, archived_at, created_at, updated_at
        FROM public.categories WHERE owner_user_id IS NULL
        WITH LOCAL CHECK OPTION
    """)
    op.execute("ALTER VIEW public.finset_system_categories OWNER TO finset_owner")


# Frozen column grants are reviewed alongside this revision, not inferred from
# future application models. In particular, result_generation is never granted.
RUNTIME_INSERT_COLUMNS = {
    "users": ("full_name", "email", "password_hash", "appearance", "currency", "date_format", "week_start_day"),
    "categories": ("owner_user_id", "name", "category_type"),
    "transactions": ("user_id", "transaction_type", "amount_kobo", "transaction_date", "category_id", "source", "description", "plan_id"),
    "plans": ("user_id", "plan_type", "expected_amount_kobo", "expected_date", "category_id", "source", "description"),
    "monthly_budgets": ("user_id", "category_id", "month_start", "allocation_kobo"),
    "budget_limits": ("user_id", "budget_id", "period_type", "start_date", "end_date", "week_start_day", "limit_kobo"),
    "budget_alerts": ("user_id", "budget_id", "budget_limit_id", "alert_type", "period_start", "period_end", "threshold_percent"),
    "login_sessions": ("user_id", "token_hash", "credential_version", "idle_expires_at", "expires_at"),
    "auth_tokens": ("user_id", "token_hash", "purpose", "target_email", "credential_version", "expires_at"),
}
RUNTIME_UPDATE_COLUMNS = {
    "users": ("full_name", "email", "password_hash", "email_verified_at", "credential_version", "appearance", "currency", "date_format", "week_start_day", "last_successful_login_at", "updated_at"),
    "categories": ("name", "archived_at", "updated_at"),
    "transactions": ("transaction_type", "amount_kobo", "transaction_date", "category_id", "source", "description", "version", "deleted_at", "recoverable_until", "updated_at"),
    "plans": ("expected_amount_kobo", "expected_date", "category_id", "source", "description", "status", "completed_at", "version", "updated_at"),
    "monthly_budgets": ("allocation_kobo", "archived_at", "version", "updated_at"),
    "budget_limits": ("start_date", "end_date", "week_start_day", "limit_kobo", "archived_at", "version", "updated_at"),
    "budget_alerts": ("read_at", "resolved_at"),
    "login_sessions": ("last_activity_at", "idle_expires_at", "revoked_at"),
    "auth_tokens": ("consumed_at", "revoked_at"),
}


def _grant_access():
    for table in TABLE_ORDER:
        op.execute(f"REVOKE ALL ON TABLE public.{table} FROM PUBLIC, finset_runtime, finset_migrator, finset_maintenance")
        op.execute(f"GRANT SELECT, DELETE ON TABLE public.{table} TO finset_runtime")
        op.execute(f"GRANT INSERT ({', '.join(RUNTIME_INSERT_COLUMNS[table])}) ON TABLE public.{table} TO finset_runtime")
        op.execute(f"GRANT UPDATE ({', '.join(RUNTIME_UPDATE_COLUMNS[table])}) ON TABLE public.{table} TO finset_runtime")
    op.execute("REVOKE ALL ON TABLE public.finset_system_categories FROM PUBLIC, finset_runtime, finset_migrator, finset_maintenance")
    op.execute("GRANT SELECT, DELETE ON TABLE public.finset_system_categories TO finset_maintenance")
    op.execute("GRANT INSERT (name, category_type) ON TABLE public.finset_system_categories TO finset_maintenance")
    op.execute("GRANT UPDATE (name, archived_at, updated_at) ON TABLE public.finset_system_categories TO finset_maintenance")


def upgrade():
    op.execute(OWNER_ASSERTION)
    _create_tables()
    _create_indexes()
    _install_enforcement()
    _grant_access()


def downgrade():
    # Deliberately destructive only to this revision's application objects.
    # External roles, their memberships, databases, and public schema remain.
    op.execute(OWNER_ASSERTION)
    op.execute("DROP VIEW public.finset_system_categories RESTRICT")
    for table, name, _ in reversed(TRIGGERS):
        op.execute(f"DROP TRIGGER {name} ON public.{table}")
    for name in reversed(FUNCTIONS):
        op.execute(f"DROP FUNCTION public.{name}() RESTRICT")
    for table in reversed(TABLE_ORDER):
        # PostgreSQL drops the table's own indexes/constraints with the table.
        op.drop_table(table, schema="public")
