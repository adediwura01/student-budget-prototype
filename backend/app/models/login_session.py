"""Server-side session record declarations, without authentication operations."""

import sqlalchemy as sa

from ..extensions import db


class LoginSession(db.Model):
    __tablename__ = "login_sessions"

    id = sa.Column(
        sa.Uuid(as_uuid=True), primary_key=True, nullable=False,
        server_default=sa.text("gen_random_uuid()"),
    )
    user_id = sa.Column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("users.id", name="fk_login_sessions_user", ondelete="CASCADE",
                      onupdate="RESTRICT", deferrable=False, match="SIMPLE"),
        nullable=False,
    )
    token_hash = sa.Column(sa.LargeBinary, nullable=False)
    credential_version = sa.Column(sa.Integer, nullable=False)
    created_at = sa.Column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"),
    )
    last_activity_at = sa.Column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"),
    )
    idle_expires_at = sa.Column(sa.DateTime(timezone=True), nullable=False)
    expires_at = sa.Column(sa.DateTime(timezone=True), nullable=False)
    revoked_at = sa.Column(sa.DateTime(timezone=True), nullable=True)

    __table_args__ = (
        sa.PrimaryKeyConstraint("id", name="pk_login_sessions", deferrable=False),
        sa.UniqueConstraint("token_hash", name="uq_login_sessions_token_hash", deferrable=False),
        sa.CheckConstraint("octet_length(token_hash) = 32", name="ck_login_sessions_hash_length"),
        sa.CheckConstraint("credential_version >= 1", name="ck_login_sessions_credential_version"),
        sa.CheckConstraint("isfinite(created_at)", name="ck_login_sessions_created_at_finite"),
        sa.CheckConstraint("isfinite(last_activity_at)", name="ck_login_sessions_last_activity_finite"),
        sa.CheckConstraint("isfinite(idle_expires_at)", name="ck_login_sessions_idle_expiry_finite"),
        sa.CheckConstraint("isfinite(expires_at)", name="ck_login_sessions_expiry_finite"),
        sa.CheckConstraint("revoked_at IS NULL OR isfinite(revoked_at)", name="ck_login_sessions_revoked_at_finite"),
        sa.CheckConstraint("last_activity_at >= created_at", name="ck_login_sessions_activity_order"),
        sa.CheckConstraint(
            "idle_expires_at > last_activity_at AND idle_expires_at <= expires_at",
            name="ck_login_sessions_idle_order",
        ),
        sa.CheckConstraint("expires_at > created_at", name="ck_login_sessions_expiry_order"),
        sa.CheckConstraint("revoked_at IS NULL OR revoked_at >= created_at", name="ck_login_sessions_revocation_order"),
        sa.Index("ix_login_sessions_user", user_id),
        sa.Index("ix_login_sessions_invalidation", sa.func.least(expires_at, idle_expires_at, revoked_at)),
    )

    user = db.relationship(
        "User", back_populates="login_sessions", foreign_keys=[user_id], viewonly=True, cascade="",
    )
