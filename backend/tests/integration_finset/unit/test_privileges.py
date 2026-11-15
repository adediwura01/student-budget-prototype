"""Synthetic PostgreSQL 18 ACLs/effective flags only; no catalog connection."""

import pytest

from ..policy import SafetyError
from ..privileges import public_permission, validate_platform_acl, validate_schema_effective, attest_platform_privileges


def acl(kind, schema, name, privilege, **extra):
    return dict(kind=kind, schema=schema, name=name, privilege=privilege,
                grantee=0, grantor=10, grantable=False, oid=100, column=None, **extra)


@pytest.mark.parametrize("row", [
    acl("schema", "pg_catalog", "pg_catalog", "USAGE"),
    acl("schema", "information_schema", "information_schema", "USAGE"),
    acl("table", "pg_catalog", "pg_roles", "SELECT"),
    acl("table", "pg_catalog", "pg_settings", "UPDATE"),
    acl("table", "information_schema", "tables", "SELECT"),
    acl("function", "pg_catalog", "lower", "EXECUTE"),
    acl("type", "pg_catalog", "uuid", "USAGE"),
    acl("language", "pg_catalog", "plpgsql", "USAGE"),
    acl("language", "pg_catalog", "sql", "USAGE"),
])
def test_legitimate_defaults_are_not_rejected(row):
    assert public_permission(row)
    validate_platform_acl([row], [1000, 1001], 1000)


@pytest.mark.parametrize("row", [
    acl("schema", "information_schema", "information_schema", "CREATE"),
    acl("table", "pg_catalog", "pg_authid", "SELECT"),
    acl("table", "pg_catalog", "pg_subscription", "SELECT"),
    acl("table", "pg_catalog", "pg_roles", "UPDATE"),
    acl("function", "pg_catalog", "pg_read_file", "EXECUTE"),
    acl("table", "information_schema", "unknown_object", "SELECT"),
    dict(acl("schema", "pg_catalog", "pg_catalog", "USAGE"), grantable=True),
    dict(acl("function", "pg_catalog", "unknown_function", "EXECUTE"), oid=20000),
])
def test_security_relevant_increases_fail_closed(row):
    assert not public_permission(row)
    with pytest.raises(SafetyError):
        validate_platform_acl([row], [1000, 1001], 1000)


def test_subscription_allows_metadata_columns_but_not_connection_options():
    safe = dict(acl("column", "pg_catalog", "pg_subscription", "SELECT"), column="oid")
    unsafe = dict(safe, column="subconninfo")
    assert public_permission(safe)
    assert not public_permission(unsafe)


@pytest.mark.parametrize("name", ["_pg_foreign_servers", "__pg_foreign_servers"])
def test_information_helper_row_and_array_type_usage_are_normal_defaults(name):
    row = dict(acl("type", "information_schema", name, "USAGE"), oid=20000)
    assert public_permission(row)


@pytest.mark.parametrize("name", ["_pg_foreign_servers", "_pg_user_mappings", "sql_parts", "transforms"])
def test_hidden_information_helpers_do_not_gain_public_select(name):
    assert not public_permission(acl("table", "information_schema", name, "SELECT"))


def test_direct_role_grants_are_rejected_even_when_redundant():
    row = dict(acl("table", "pg_catalog", "pg_roles", "SELECT"), grantee=1001)
    with pytest.raises(SafetyError):
        validate_platform_acl([row], [1000, 1001], 1000)


def test_owner_implicit_toast_storage_is_not_a_public_grant():
    row = dict(acl("table", "pg_toast", "pg_toast_synthetic", "SELECT"),
               grantee=1000, grantor=1000, storage_owned=True)
    validate_platform_acl([row], [1000, 1001], 1000)
    with pytest.raises(SafetyError):
        validate_platform_acl([dict(row, grantee=0)], [1000, 1001], 1000)


@pytest.mark.parametrize("field", ["create", "create_grantable"])
def test_effective_create_through_public_or_membership_is_rejected(field):
    row = dict(schema="information_schema", create=False, create_grantable=False)
    row[field] = True
    with pytest.raises(SafetyError):
        validate_schema_effective([row])


def test_attestation_reads_only_synthetic_metadata():
    statements = []
    role_ids = {"finset_owner": 1000, "finset_runtime": 1001}
    responses = [[dict(rolname=role, schema=schema, create=False, create_grantable=False)
                  for role in role_ids for schema in ("pg_catalog", "information_schema", "pg_toast")],
                 [acl("schema", "information_schema", "information_schema", "USAGE")], []]
    def query(connection, statement, params):
        statements.append(statement)
        assert "SELECT" in statement and "INSERT INTO" not in statement
        return responses.pop(0)
    attest_platform_privileges(object(), role_ids, query=query)
    assert len(statements) == 3 and not responses


def test_incomplete_privilege_metadata_fails_closed():
    with pytest.raises(SafetyError, match="incomplete"):
        attest_platform_privileges(object(), {"finset_owner": 1000}, query=lambda *args: [])
