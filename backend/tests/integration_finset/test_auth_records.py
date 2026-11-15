"""Credential-row integrity, not current-time TTL or one-time redemption policy.

Known limitation: the current trigger permits rewriting a non-NULL consumed_at.
These tests require only that it cannot be cleared; they do not endorse timestamp
rewriting as a product rule or attempt to fix it in production sources.
"""

from datetime import timedelta
from hashlib import sha256

import pytest


pytestmark = [pytest.mark.integration, pytest.mark.finset_integration]

AUTH_TABLES = [("login_session", "login_sessions"), ("token", "auth_tokens")]
TOKEN_PURPOSES = ["verify_email", "reset_password", "change_email"]


@pytest.mark.parametrize("builder,purpose", [
    ("login_session", None),
    ("token", "verify_email"),
    ("token", "reset_password"),
    ("token", "change_email"),
])
def test_auth_record_crud_uses_safe_snapshots(runtime, data, case, builder, purpose):
    user = data.user()
    now = runtime.clock()
    token_hash = sha256(case.label("auth_hash").encode("ascii")).digest()
    assert len(token_hash) == 32
    options = {
        "token_hash": token_hash,
        "credential_version": user.values["credential_version"],
        "expires_at": now + timedelta(hours=2),
    }
    if builder == "login_session":
        record = data.login_session(user, idle_expires_at=now + timedelta(minutes=30), **options)
        columns = {
            "id", "user_id", "credential_version", "created_at", "last_activity_at",
            "idle_expires_at", "expires_at", "revoked_at",
        }
    else:
        target = None
        if purpose == "verify_email":
            target = user.values["email"]
        elif purpose == "change_email":
            target = case.email("token_target")
        record = data.token(user, purpose=purpose, target_email=target, **options)
        columns = {
            "id", "user_id", "purpose", "target_email", "credential_version",
            "created_at", "expires_at", "consumed_at", "revoked_at",
        }
    row = runtime.get(record)
    assert set(row) == columns
    assert "token_hash" not in record.values
    assert "password_hash" not in user.values
    assert row["id"] == record.id
    assert row["user_id"] == record.owner_id == user.id
    assert row["created_at"] == now
    assert row["expires_at"].utcoffset() is not None
    assert row["expires_at"] > row["created_at"]
    assert row["revoked_at"] is None
    if builder == "login_session":
        assert row["last_activity_at"] == now
        assert row["last_activity_at"] < row["idle_expires_at"] <= row["expires_at"]
    else:
        assert row["purpose"] == purpose
        assert row["target_email"] == target
        assert row["consumed_at"] is None

    record = runtime.update(record, revoked_at=now)
    row = runtime.get(record)
    assert row["revoked_at"] == now
    assert "token_hash" not in row
    assert runtime.rows(record.table, user_id=user.id) == [row]
    runtime.check_constraints()
    # Exercise explicit DELETEs, never an ON DELETE CASCADE or fixture cleanup.
    assert runtime.delete(record) == 1
    assert runtime.get(record) is None
    assert runtime.count(record.table, user_id=user.id) == 0
    assert runtime.delete(user) == 1
    assert runtime.get(user) is None


@pytest.mark.parametrize("builder,table", AUTH_TABLES)
@pytest.mark.parametrize("length,sqlstate", [(None, "23502"), (0, "23514"), (31, "23514"), (33, "23514")])
def test_auth_hash_requires_exactly_32_bytes(runtime, data, builder, table, length, sqlstate):
    user = data.user()
    token_hash = None if length is None else b"x" * length
    constraint = None if length is None else f"ck_{table}_hash_length"
    with runtime.rejects(sqlstate, constraint=constraint):
        getattr(data, builder)(user, token_hash=token_hash)


@pytest.mark.parametrize("builder,table", AUTH_TABLES)
def test_auth_hash_is_unique_across_users(runtime, data, case, builder, table):
    first_user = data.user()
    second_user = data.user()
    token_hash = sha256(case.label("unique_hash").encode("ascii")).digest()
    assert len(token_hash) == 32
    original = getattr(data, builder)(first_user, token_hash=token_hash)
    # Separate users avoid also violating the auth-token outstanding-purpose slot.
    with runtime.rejects("23505", constraint=f"uq_{table}_token_hash"):
        getattr(data, builder)(second_user, token_hash=token_hash)
    assert runtime.get(original) is not None
    assert runtime.count(table, user_id=second_user.id) == 0


def test_token_rejects_unknown_purpose(runtime, data, case):
    user = data.user()
    # Both the enum and its target-shape CHECK can reject an unknown purpose.
    with runtime.rejects("23514"):
        runtime.insert(
            "auth_tokens", user_id=user.id,
            token_hash=sha256(case.label("purpose_hash").encode("ascii")).digest(),
            purpose="unknown", target_email=None, credential_version=1,
            expires_at=runtime.clock() + timedelta(hours=1),
        )


@pytest.mark.parametrize("purpose", ["verify_email", "change_email"])
@pytest.mark.parametrize("variant", ["null", "empty", "uppercase", "padded"])
def test_email_token_requires_a_normalized_target(runtime, data, case, purpose, variant):
    user = data.user()
    target = case.email("target")
    invalid = {
        "null": None, "empty": "", "uppercase": target.upper(), "padded": f" {target} ",
    }[variant]
    with runtime.rejects("23514", constraint="ck_auth_tokens_target_email"):
        data.token(user, purpose=purpose, target_email=invalid)


def test_password_reset_token_requires_null_target(runtime, data, case):
    user = data.user()
    with runtime.rejects("23514", constraint="ck_auth_tokens_target_email"):
        data.token(user, purpose="reset_password", target_email=case.email("reset_target"))


@pytest.mark.parametrize("purpose", TOKEN_PURPOSES)
def test_outstanding_token_slot_is_per_user_and_purpose(runtime, data, purpose):
    user = data.user()
    original = data.token(user, purpose=purpose)
    with runtime.rejects("23505", constraint="uq_auth_tokens_outstanding_purpose"):
        data.token(user, purpose=purpose)
    other_purpose = "verify_email" if purpose == "reset_password" else "reset_password"
    different_purpose = data.token(user, purpose=other_purpose)
    other_user = data.user()
    different_owner = data.token(other_user, purpose=purpose)
    assert len({original.id, different_purpose.id, different_owner.id}) == 3
    assert runtime.count("auth_tokens", user_id=user.id, consumed_at=None, revoked_at=None) == 2


@pytest.mark.parametrize("terminal,other_terminal", [
    ("consumed_at", "revoked_at"),
    ("revoked_at", "consumed_at"),
])
def test_token_terminal_state_cannot_reopen_and_releases_slot(runtime, data, terminal, other_terminal):
    user = data.user()
    token = data.token(user)
    token = runtime.update(token, **{terminal: runtime.clock()})
    with runtime.rejects("23514", constraint="ck_auth_tokens_terminal_state"):
        runtime.update(token, **{other_terminal: runtime.clock()})
    with runtime.rejects("23514"):
        runtime.update(token, **{terminal: None})
    replacement = data.token(user)
    assert token.id != replacement.id
    assert runtime.get(token)[terminal] == runtime.clock()
    assert runtime.get(token)[other_terminal] is None
    assert runtime.count("auth_tokens", user_id=user.id, consumed_at=None, revoked_at=None) == 1
    runtime.check_constraints()


def test_user_credential_version_can_stay_or_increase_but_not_decrease(runtime, data, case):
    user = data.user()
    version = user.values["credential_version"] + 2
    user = runtime.update(user, credential_version=version)
    user = runtime.update(user, credential_version=version, full_name=case.label("same_version"))
    assert runtime.get(user)["credential_version"] == version
    for invalid in (version - 1, 0, -1):
        # A positive decrease isolates the lifecycle trigger from the >= 1 CHECK.
        with runtime.rejects("23514"):
            runtime.update(user, credential_version=invalid)
        assert runtime.get(user)["credential_version"] == version


@pytest.mark.parametrize("builder,table", AUTH_TABLES)
@pytest.mark.parametrize("version,sqlstate", [(None, "23502"), (0, "23514"), (-1, "23514")])
def test_auth_credential_version_is_required_and_positive(runtime, data, builder, table, version, sqlstate):
    user = data.user()
    constraint = None if version is None else f"ck_{table}_credential_version"
    with runtime.rejects(sqlstate, constraint=constraint):
        getattr(data, builder)(user, credential_version=version)


def test_session_activity_and_idle_deadline_are_nondecreasing(runtime, data):
    user = data.user()
    now = runtime.clock()
    session = data.login_session(
        user, idle_expires_at=now + timedelta(minutes=30), expires_at=now + timedelta(hours=2),
    )
    activity = now + timedelta(minutes=5)
    idle = now + timedelta(hours=1)
    session = runtime.update(session, last_activity_at=activity, idle_expires_at=idle)
    session = runtime.update(session, last_activity_at=activity, idle_expires_at=idle)
    for changes in (
        {"last_activity_at": activity - timedelta(seconds=1)},
        {"idle_expires_at": idle - timedelta(seconds=1)},
    ):
        # Each decrease would still satisfy the ordinary timestamp-order CHECKs.
        with runtime.rejects("23514"):
            runtime.update(session, **changes)
        row = runtime.get(session)
        assert row["last_activity_at"] == activity
        assert row["idle_expires_at"] == idle
    with runtime.rejects("23514", constraint="ck_login_sessions_idle_order"):
        runtime.update(session, last_activity_at=idle)
    runtime.check_constraints()


@pytest.mark.parametrize("idle_minutes", [-1, 0, 121])
def test_session_idle_deadline_must_follow_activity_and_not_exceed_expiry(runtime, data, idle_minutes):
    user = data.user()
    now = runtime.clock()
    with runtime.rejects("23514", constraint="ck_login_sessions_idle_order"):
        data.login_session(
            user, idle_expires_at=now + timedelta(minutes=idle_minutes),
            expires_at=now + timedelta(hours=2),
        )


def test_revoked_session_cannot_be_reopened(runtime, data):
    user = data.user()
    session = data.login_session(user)
    session = runtime.update(session, revoked_at=runtime.clock())
    with runtime.rejects("23514"):
        runtime.update(session, revoked_at=None)
    assert runtime.get(session)["revoked_at"] == runtime.clock()


@pytest.mark.parametrize("seconds", [-1, 0])
def test_token_expiry_must_follow_creation(runtime, data, seconds):
    user = data.user()
    with runtime.rejects("23514", constraint="ck_auth_tokens_expiry_order"):
        data.token(user, expires_at=runtime.clock() + timedelta(seconds=seconds))


@pytest.mark.parametrize("builder,column,constraint", [
    ("login_session", "revoked_at", "ck_login_sessions_revocation_order"),
    ("token", "consumed_at", "ck_auth_tokens_consumption_order"),
    ("token", "revoked_at", "ck_auth_tokens_revocation_order"),
])
def test_auth_terminal_timestamps_cannot_precede_creation(runtime, data, builder, column, constraint):
    user = data.user()
    record = getattr(data, builder)(user)
    with runtime.rejects("23514", constraint=constraint):
        runtime.update(record, **{column: runtime.clock() - timedelta(seconds=1)})
