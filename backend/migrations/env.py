"""Explicit owner-role migrations; offline compilation never creates an engine."""

from logging.config import fileConfig
import os

from alembic import context
import sqlalchemy as sa

from app.extensions import db


config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = db.metadata

# These are execution-time preconditions, emitted but never evaluated offline.
# Provisioning is deliberately external: no role/schema ownership is repaired here.
ROLE_PREFLIGHT_SQL = """
DO $finset_roles$
DECLARE
    role_name name;
    role_row record;
    edge record;
    owner_oid oid;
    migrator_oid oid;
    public_oid oid;
BEGIN
    FOREACH role_name IN ARRAY ARRAY[
        'finset_runtime', 'finset_migrator', 'finset_owner', 'finset_maintenance'
    ] LOOP
        SELECT * INTO role_row FROM pg_catalog.pg_roles WHERE rolname = role_name;
        IF NOT FOUND THEN
            RAISE EXCEPTION USING ERRCODE = '55000',
                MESSAGE = 'Required externally provisioned role is missing: ' || role_name;
        END IF;
        IF role_row.rolcanlogin OR role_row.rolsuper OR role_row.rolcreatedb
           OR role_row.rolcreaterole OR role_row.rolreplication OR role_row.rolbypassrls THEN
            RAISE EXCEPTION USING ERRCODE = '42501',
                MESSAGE = 'FinSet group role has inappropriate attributes: ' || role_name;
        END IF;
    END LOOP;

    FOR edge IN SELECT * FROM (VALUES
        ('finset_runtime', 'finset_owner'),
        ('finset_runtime', 'finset_migrator'),
        ('finset_runtime', 'finset_maintenance'),
        ('finset_maintenance', 'finset_runtime'),
        ('finset_maintenance', 'finset_migrator'),
        ('finset_maintenance', 'finset_owner')
    ) AS forbidden(member_name, target_name) LOOP
        IF pg_catalog.pg_has_role(CAST(edge.member_name AS name), CAST(edge.target_name AS name), 'MEMBER') THEN
            RAISE EXCEPTION USING ERRCODE = '42501',
                MESSAGE = 'Forbidden FinSet role membership: ' || edge.member_name || ' -> ' || edge.target_name;
        END IF;
    END LOOP;

    SELECT oid INTO owner_oid FROM pg_catalog.pg_roles WHERE rolname = 'finset_owner';
    SELECT oid INTO migrator_oid FROM pg_catalog.pg_roles WHERE rolname = 'finset_migrator';
    IF NOT pg_catalog.pg_has_role('finset_migrator', 'finset_owner', 'SET')
       OR pg_catalog.pg_has_role('finset_migrator', 'finset_owner', 'USAGE')
       OR pg_catalog.pg_has_role('finset_migrator', 'finset_maintenance', 'USAGE')
       OR pg_catalog.pg_has_role('finset_owner', 'finset_maintenance', 'USAGE') THEN
        RAISE EXCEPTION 'Migrator requires explicit owner SET without inherited owner/maintenance rights'
            USING ERRCODE = '42501';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_auth_members
        WHERE roleid = owner_oid AND member = migrator_oid
          AND set_option AND NOT inherit_option AND NOT admin_option
    ) OR EXISTS (
        SELECT 1 FROM pg_catalog.pg_auth_members
        WHERE roleid = owner_oid AND member = migrator_oid
          AND (inherit_option OR admin_option)
    ) THEN
        RAISE EXCEPTION 'Provision migrator-to-owner SET TRUE, INHERIT FALSE, ADMIN FALSE externally'
            USING ERRCODE = '42501';
    END IF;

    SELECT * INTO role_row FROM pg_catalog.pg_roles WHERE rolname = session_user;
    IF NOT role_row.rolcanlogin OR role_row.rolsuper OR role_row.rolcreatedb OR role_row.rolcreaterole
       OR role_row.rolreplication OR role_row.rolbypassrls
       OR NOT pg_catalog.pg_has_role(session_user, 'finset_migrator', 'MEMBER')
       OR NOT pg_catalog.pg_has_role(session_user, 'finset_owner', 'SET')
       OR pg_catalog.pg_has_role(session_user, 'finset_owner', 'USAGE')
       OR pg_catalog.pg_has_role(session_user, 'finset_maintenance', 'USAGE')
       OR pg_catalog.pg_has_role(session_user, 'finset_runtime', 'MEMBER') THEN
        RAISE EXCEPTION 'Use a separate restricted migration login, not runtime/owner/administrator credentials'
            USING ERRCODE = '42501';
    END IF;

    SELECT oid INTO public_oid FROM pg_catalog.pg_namespace
    WHERE nspname = 'public' AND nspowner = owner_oid;
    IF public_oid IS NULL THEN
        RAISE EXCEPTION 'DBA must provision public schema ownership to finset_owner first'
            USING ERRCODE = '55000';
    END IF;
    -- Inspect the PUBLIC pseudo-role directly, including PostgreSQL's default ACL.
    -- Reject unsafe provisioning; do not change any schema grants here.
    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_namespace AS ns
        CROSS JOIN LATERAL pg_catalog.aclexplode(
            COALESCE(ns.nspacl, pg_catalog.acldefault('n', ns.nspowner))
        ) AS acl
        WHERE ns.oid = public_oid AND acl.grantee = 0 AND acl.privilege_type = 'CREATE'
    ) THEN
        RAISE EXCEPTION 'PUBLIC must not have CREATE on schema public'
            USING ERRCODE = '42501';
    END IF;
    FOREACH role_name IN ARRAY ARRAY['finset_runtime', 'finset_maintenance', 'finset_migrator'] LOOP
        IF pg_catalog.has_schema_privilege(role_name, public_oid, 'CREATE') THEN
            RAISE EXCEPTION USING ERRCODE = '42501',
                MESSAGE = 'Ordinary FinSet role must not have schema CREATE: ' || role_name;
        END IF;
    END LOOP;
    IF NOT pg_catalog.has_schema_privilege('finset_runtime', public_oid, 'USAGE')
       OR NOT pg_catalog.has_schema_privilege('finset_maintenance', public_oid, 'USAGE')
       OR pg_catalog.has_schema_privilege(session_user, public_oid, 'CREATE') THEN
        RAISE EXCEPTION 'Provision limited schema USAGE, without ordinary migration-login CREATE'
            USING ERRCODE = '42501';
    END IF;

    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_default_acl AS defaults
        CROSS JOIN LATERAL pg_catalog.aclexplode(defaults.defaclacl) AS permission
        WHERE defaults.defaclrole = owner_oid
          AND defaults.defaclnamespace IN (0, public_oid)
          AND defaults.defaclobjtype IN ('r', 'f')
          AND permission.grantee <> owner_oid
          AND NOT (defaults.defaclobjtype = 'f' AND permission.grantee = 0)
    ) THEN
        RAISE EXCEPTION 'Owner defaults must not expose tables or grant function execution beyond default PUBLIC'
            USING ERRCODE = '42501';
    END IF;
END;
$finset_roles$;
"""


def run_migrations_offline():
    context.configure(
        dialect_name="postgresql",
        dialect_opts={"paramstyle": "named"},
        target_metadata=target_metadata,
        literal_binds=True,
        transactional_ddl=True,
        version_table_schema="public",
        compare_type=True,
    )
    with context.begin_transaction():
        context.execute("SET LOCAL search_path = pg_catalog, pg_temp")
        context.execute(ROLE_PREFLIGHT_SQL)
        context.execute("SET LOCAL ROLE finset_owner")
        context.execute("SET LOCAL search_path = public, pg_catalog, pg_temp")
        context.run_migrations()


def run_migrations_online():
    # Never reuse Flask's runtime engine/credentials for administrative operations.
    value = os.environ.get("FINSET_MIGRATION_DATABASE_URL")
    if not value:
        raise RuntimeError("FINSET_MIGRATION_DATABASE_URL is required for an authorized online migration.")
    try:
        url = sa.engine.make_url(value)
    except (sa.exc.ArgumentError, ValueError):
        raise RuntimeError("The migration database URL is invalid.") from None
    if url.drivername != "postgresql+psycopg" or not url.host or not url.database or not url.username:
        raise RuntimeError("Use a PostgreSQL/psycopg URL with a separately provisioned migration login.")
    engine = sa.create_engine(url, poolclass=sa.pool.NullPool)
    try:
        with engine.connect() as connection:
            # Owner assumption precedes Alembic's version-table creation as well.
            with connection.begin():
                connection.exec_driver_sql("SET LOCAL search_path = pg_catalog, pg_temp")
                connection.exec_driver_sql(ROLE_PREFLIGHT_SQL)
                connection.exec_driver_sql("SET LOCAL ROLE finset_owner")
                connection.exec_driver_sql("SET LOCAL search_path = public, pg_catalog, pg_temp")
                engine.dialect.default_schema_name = "public"
                context.configure(
                    connection=connection,
                    target_metadata=target_metadata,
                    version_table_schema="public",
                    compare_type=True,
                )
                with context.begin_transaction():
                    context.run_migrations()
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
