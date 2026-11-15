"""Purpose-bound token declarations; token issuance and redemption are not implemented."""

import sqlalchemy as sa

from ..extensions import db


class AuthToken(db.Model):
    __tablename__ = "auth_tokens"

    id = sa.Column(
        sa.Uuid(as_uuid=True), primary_key=True, nullable=False,
        server_default=sa.text("gen_random_uuid()"),
    )
    user_id = sa.Column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("users.id", name="fk_auth_tokens_user", ondelete="CASCADE",
                      onupdate="RESTRICT", deferrable=False, match="SIMPLE"),
        nullable=False,
    )
    token_hash = sa.Column(sa.LargeBinary, nullable=False)
    purpose = sa.Column(sa.String(20), nullable=False)
    target_email = sa.Column(sa.String(254), nullable=True)
    credential_version = sa.Column(sa.Integer, nullable=False)
    created_at = sa.Column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"),
    )
    expires_at = sa.Column(sa.DateTime(timezone=True), nullable=False)
    consumed_at = sa.Column(sa.DateTime(timezone=True), nullable=True)
    revoked_at = sa.Column(sa.DateTime(timezone=True), nullable=True)

    __table_args__ = (
        sa.PrimaryKeyConstraint("id", name="pk_auth_tokens", deferrable=False),
        sa.UniqueConstraint("token_hash", name="uq_auth_tokens_token_hash", deferrable=False),
        sa.CheckConstraint("octet_length(token_hash) = 32", name="ck_auth_tokens_hash_length"),
        sa.CheckConstraint("purpose IN ('verify_email', 'reset_password', 'change_email')", name="ck_auth_tokens_purpose"),
        sa.CheckConstraint(
            "(purpose IN ('verify_email', 'change_email') AND target_email IS NOT NULL "
            "AND char_length(target_email) > 0 AND target_email = lower(btrim(target_email))) OR "
            "(purpose = 'reset_password' AND target_email IS NULL)",
            name="ck_auth_tokens_target_email",
        ),
        sa.CheckConstraint("credential_version >= 1", name="ck_auth_tokens_credential_version"),
        sa.CheckConstraint("isfinite(created_at)", name="ck_auth_tokens_created_at_finite"),
        sa.CheckConstraint("isfinite(expires_at)", name="ck_auth_tokens_expiry_finite"),
        sa.CheckConstraint("expires_at > created_at", name="ck_auth_tokens_expiry_order"),
        sa.CheckConstraint("consumed_at IS NULL OR isfinite(consumed_at)", name="ck_auth_tokens_consumed_at_finite"),
        sa.CheckConstraint("consumed_at IS NULL OR consumed_at >= created_at", name="ck_auth_tokens_consumption_order"),
        sa.CheckConstraint("revoked_at IS NULL OR isfinite(revoked_at)", name="ck_auth_tokens_revoked_at_finite"),
        sa.CheckConstraint("revoked_at IS NULL OR revoked_at >= created_at", name="ck_auth_tokens_revocation_order"),
        sa.CheckConstraint("consumed_at IS NULL OR revoked_at IS NULL", name="ck_auth_tokens_terminal_state"),
        sa.Index(
            "uq_auth_tokens_outstanding_purpose", user_id, purpose, unique=True,
            postgresql_where=sa.and_(consumed_at.is_(None), revoked_at.is_(None)),
        ),
        sa.Index("ix_auth_tokens_user", user_id),
        sa.Index("ix_auth_tokens_invalidation", sa.func.least(expires_at, consumed_at, revoked_at)),
    )

    user = db.relationship(
        "User", back_populates="auth_tokens", foreign_keys=[user_id], viewonly=True, cascade="",
    )
