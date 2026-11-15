"""PostgreSQL 18 platform privilege policy, derived from initdb sources, not observed ACLs.

Sources: PostgreSQL 18 postgres.bki, system_views.sql, system_functions.sql and
information_schema.sql. Normal metadata SELECT, builtin EXECUTE/type USAGE,
schema USAGE, and pg_settings SELECT/UPDATE are legitimate PUBLIC defaults.
Restricted catalog rows/functions and all extra persistent-schema CREATE are not.
This attests privileges, not the integrity of PostgreSQL's executable installation.
"""

from .policy import SafetyError


CATALOG_TABLES = frozenset("""
pg_proc pg_type pg_attribute pg_class pg_attrdef pg_constraint pg_inherits pg_index
pg_operator pg_opfamily pg_opclass pg_am pg_amop pg_amproc pg_language pg_largeobject_metadata
pg_largeobject pg_aggregate pg_statistic pg_statistic_ext pg_statistic_ext_data pg_rewrite
pg_trigger pg_event_trigger pg_description pg_cast pg_enum pg_namespace pg_conversion
pg_depend pg_database pg_db_role_setting pg_tablespace pg_authid pg_auth_members pg_shdepend
pg_shdescription pg_ts_config pg_ts_config_map pg_ts_dict pg_ts_parser pg_ts_template pg_extension
pg_foreign_data_wrapper pg_foreign_server pg_user_mapping pg_foreign_table pg_policy
pg_replication_origin pg_default_acl pg_init_privs pg_seclabel pg_shseclabel pg_collation
pg_parameter_acl pg_partitioned_table pg_range pg_transform pg_sequence pg_publication
pg_publication_namespace pg_publication_rel pg_subscription pg_subscription_rel
""".split())
CATALOG_VIEWS = frozenset("""
pg_roles pg_shadow pg_group pg_user pg_policies pg_rules pg_views pg_tables pg_matviews
pg_indexes pg_sequences pg_stats pg_stats_ext pg_stats_ext_exprs pg_publication_tables
pg_locks pg_cursors pg_available_extensions pg_available_extension_versions pg_prepared_xacts
pg_prepared_statements pg_seclabels pg_settings pg_file_settings pg_hba_file_rules
pg_ident_file_mappings pg_timezone_abbrevs pg_timezone_names pg_config pg_shmem_allocations
pg_shmem_allocations_numa pg_backend_memory_contexts pg_stat_all_tables pg_stat_xact_all_tables
pg_stat_sys_tables pg_stat_xact_sys_tables pg_stat_user_tables pg_stat_xact_user_tables
pg_statio_all_tables pg_statio_sys_tables pg_statio_user_tables pg_stat_all_indexes
pg_stat_sys_indexes pg_stat_user_indexes pg_statio_all_indexes pg_statio_sys_indexes
pg_statio_user_indexes pg_statio_all_sequences pg_statio_sys_sequences pg_statio_user_sequences
pg_stat_activity pg_stat_replication pg_stat_slru pg_stat_wal_receiver pg_stat_recovery_prefetch
pg_stat_subscription pg_stat_ssl pg_stat_gssapi pg_replication_slots pg_stat_replication_slots
pg_stat_database pg_stat_database_conflicts pg_stat_user_functions pg_stat_xact_user_functions
pg_stat_archiver pg_stat_bgwriter pg_stat_checkpointer pg_stat_io pg_stat_wal
pg_stat_progress_analyze pg_stat_progress_vacuum pg_stat_progress_cluster
pg_stat_progress_create_index pg_stat_progress_basebackup pg_stat_progress_copy pg_user_mappings
pg_replication_origin_status pg_stat_subscription_stats pg_wait_events pg_aios
""".split())
INFORMATION_RELATIONS = frozenset("""
information_schema_catalog_name applicable_roles administrable_role_authorizations attributes
character_sets check_constraint_routine_usage check_constraints collations
collation_character_set_applicability column_column_usage column_domain_usage column_privileges
column_udt_usage columns constraint_column_usage constraint_table_usage domain_constraints
domain_udt_usage domains enabled_roles key_column_usage parameters referential_constraints
role_column_grants routine_column_usage routine_privileges role_routine_grants
routine_routine_usage routine_sequence_usage routine_table_usage routines schemata sequences
sql_features sql_implementation_info sql_parts sql_sizing table_constraints table_privileges
role_table_grants tables transforms triggered_update_columns triggers udt_privileges
role_udt_grants usage_privileges role_usage_grants user_defined_types view_column_usage
view_routine_usage view_table_usage views data_type_privileges element_types _pg_foreign_table_columns
column_options _pg_foreign_data_wrappers foreign_data_wrapper_options foreign_data_wrappers
_pg_foreign_servers foreign_server_options foreign_servers _pg_foreign_tables foreign_table_options
foreign_tables _pg_user_mappings user_mapping_options user_mappings
""".split())
INFORMATION_FUNCTIONS = frozenset("""
_pg_expandarray _pg_index_position _pg_truetypid _pg_truetypmod _pg_char_max_length
_pg_char_octet_length _pg_numeric_precision _pg_numeric_precision_radix _pg_numeric_scale
_pg_datetime_precision _pg_interval_type
""".split())
INFORMATION_TYPES = frozenset(("cardinal_number", "character_data", "sql_identifier", "time_stamp", "yes_or_no"))
INFORMATION_PUBLIC_SELECT = frozenset(name for name in INFORMATION_RELATIONS
                                      if not name.startswith("_") and name not in ("sql_parts", "transforms"))
RESTRICTED_RELATIONS = frozenset("""
pg_authid pg_shadow pg_statistic pg_statistic_ext_data pg_largeobject pg_user_mapping
pg_file_settings pg_hba_file_rules pg_ident_file_mappings pg_config pg_shmem_allocations
pg_shmem_allocations_numa pg_backend_memory_contexts pg_replication_origin_status pg_subscription pg_aios
""".split())
SUBSCRIPTION_COLUMNS = frozenset("""
oid subdbid subskiplsn subname subowner subenabled subbinary substream subtwophasestate
subdisableonerr subpasswordrequired subrunasowner subfailover subslotname subsynccommit
subpublications suborigin
""".split())
# Every overload of these names is revoked by PostgreSQL 18 initdb SQL.
RESTRICTED_FUNCTIONS = frozenset("""
pg_backup_start pg_backup_stop pg_create_restore_point pg_switch_wal pg_log_standby_snapshot
pg_wal_replay_pause pg_wal_replay_resume pg_rotate_logfile pg_reload_conf pg_current_logfile
pg_promote pg_stat_reset pg_stat_reset_shared pg_stat_reset_slru pg_stat_reset_single_table_counters
pg_stat_reset_single_function_counters pg_stat_reset_backend_stats pg_stat_reset_replication_slot
pg_stat_have_stats pg_stat_reset_subscription_stats lo_import lo_export pg_ls_logdir pg_ls_waldir
pg_ls_archive_statusdir pg_ls_summariesdir pg_ls_tmpdir pg_read_file pg_read_binary_file
pg_replication_origin_advance pg_replication_origin_create pg_replication_origin_drop
pg_replication_origin_oid pg_replication_origin_progress pg_replication_origin_session_is_setup
pg_replication_origin_session_progress pg_replication_origin_session_reset
pg_replication_origin_session_setup pg_replication_origin_xact_reset pg_replication_origin_xact_setup
pg_show_replication_origin_status pg_stat_file pg_ls_dir pg_log_backend_memory_contexts
pg_ls_logicalsnapdir pg_ls_logicalmapdir pg_ls_replslotdir pg_show_all_file_settings
pg_hba_file_rules pg_ident_file_mappings pg_config pg_get_shmem_allocations
pg_get_shmem_allocations_numa pg_get_backend_memory_contexts pg_get_aios
""".split())
PLPGSQL_FUNCTIONS = frozenset(("plpgsql_call_handler", "plpgsql_inline_handler", "plpgsql_validator"))


def public_permission(row):
    """True only for a documented baseline privilege; no baseline is learned here."""
    kind, schema, name, permission = (row[key] for key in ("kind", "schema", "name", "privilege"))
    column = row.get("column")
    if row.get("grantable"):
        return False
    if kind == "schema":
        return schema in ("pg_catalog", "information_schema") and permission == "USAGE"
    if kind in ("table", "column"):
        if schema == "information_schema":
            return name in INFORMATION_PUBLIC_SELECT and permission == "SELECT"
        if schema != "pg_catalog":
            return False
        if name == "pg_subscription":
            return kind == "column" and column in SUBSCRIPTION_COLUMNS and permission == "SELECT"
        if name in RESTRICTED_RELATIONS:
            return False
        if name == "pg_settings":
            return permission in ("SELECT", "UPDATE")
        return name in CATALOG_TABLES | CATALOG_VIEWS and permission == "SELECT"
    if kind == "function":
        if permission != "EXECUTE" or name in RESTRICTED_FUNCTIONS:
            return False
        if schema == "information_schema":
            return name in INFORMATION_FUNCTIONS
        return schema == "pg_catalog" and (row.get("oid", 16384) < 16384 or name in PLPGSQL_FUNCTIONS)
    if kind == "type":
        if permission != "USAGE":
            return False
        if schema == "information_schema":
            names = INFORMATION_TYPES | INFORMATION_RELATIONS
            return name in names or name.startswith("_") and name[1:] in names
        return schema == "pg_catalog" and (row.get("oid", 16384) < 16384
                                            or name in CATALOG_TABLES | CATALOG_VIEWS
                                            or name.startswith("_") and name[1:] in CATALOG_TABLES | CATALOG_VIEWS)
    return kind == "language" and name in ("sql", "plpgsql") and permission == "USAGE"


def validate_platform_acl(rows, role_oids, owner_oid):
    for row in rows:
        if row["grantee"] == 0:
            if not public_permission(row):
                raise SafetyError("Unexpected security-relevant PUBLIC platform privilege.")
        elif row["grantee"] in role_oids:
            # Only implicit ownership of this application's storage relations is normal.
            if not (row["grantee"] == owner_oid and row.get("storage_owned")
                    and row["grantor"] == owner_oid and not row["grantable"]):
                raise SafetyError("Unexpected direct platform privilege for an integration role.")


def validate_schema_effective(rows):
    for row in rows:
        if row["schema"] != "public" and (row["create"] or row["create_grantable"]):
            raise SafetyError("An integration role can create objects outside the approved schema.")


def attest_platform_privileges(connection, roles, *, query):
    """Catalog metadata only, confined to the connected integration database."""
    ids = list(roles.values())
    owner = roles["finset_owner"]
    schemas = query(connection, """
        SELECT r.rolname, n.nspname AS schema,
               pg_catalog.has_schema_privilege(r.oid,n.oid,'CREATE') AS create,
               pg_catalog.has_schema_privilege(r.oid,n.oid,'CREATE WITH GRANT OPTION') AS create_grantable
        FROM pg_catalog.pg_roles r CROSS JOIN pg_catalog.pg_namespace n
        WHERE r.oid=ANY(%s) AND n.nspname <> 'public'
          AND n.nspname !~ '^pg_temp_' AND n.nspname !~ '^pg_toast_temp_'
    """, (ids,))
    required = {(name, schema) for name in roles for schema in ("pg_catalog", "information_schema", "pg_toast")}
    if not required <= {(row["rolname"], row["schema"]) for row in schemas}:
        raise SafetyError("Platform effective-privilege metadata is incomplete.")
    validate_schema_effective(schemas)
    rows = query(connection, """
        SELECT 'schema' AS kind,n.nspname AS schema,n.nspname AS name,NULL::text AS column,
               n.oid,a.grantor,a.grantee,a.privilege_type AS privilege,a.is_grantable AS grantable,false AS storage_owned
        FROM pg_catalog.pg_namespace n
        CROSS JOIN LATERAL pg_catalog.aclexplode(COALESCE(n.nspacl,pg_catalog.acldefault('n',n.nspowner))) a
        WHERE n.nspname<>'public' AND n.nspname !~ '^pg_temp_' AND n.nspname !~ '^pg_toast_temp_'
        UNION ALL
        SELECT 'table',n.nspname,c.relname,NULL,c.oid,a.grantor,a.grantee,a.privilege_type,a.is_grantable,
               n.nspname='pg_toast' AND c.relowner=%s
        FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
        CROSS JOIN LATERAL pg_catalog.aclexplode(COALESCE(c.relacl,pg_catalog.acldefault('r',c.relowner))) a
        WHERE n.nspname<>'public' AND n.nspname !~ '^pg_temp_' AND n.nspname !~ '^pg_toast_temp_'
          AND c.relkind IN ('r','v','m','f')
        UNION ALL
        SELECT 'column',n.nspname,c.relname,col.attname,c.oid,a.grantor,a.grantee,a.privilege_type,a.is_grantable,false
        FROM pg_catalog.pg_attribute col JOIN pg_catalog.pg_class c ON c.oid=col.attrelid
        JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
        CROSS JOIN LATERAL pg_catalog.aclexplode(col.attacl) a WHERE n.nspname<>'public'
        UNION ALL
        SELECT 'function',n.nspname,p.proname,NULL,p.oid,a.grantor,a.grantee,a.privilege_type,a.is_grantable,false
        FROM pg_catalog.pg_proc p JOIN pg_catalog.pg_namespace n ON n.oid=p.pronamespace
        CROSS JOIN LATERAL pg_catalog.aclexplode(COALESCE(p.proacl,pg_catalog.acldefault('f',p.proowner))) a
        WHERE n.nspname<>'public'
        UNION ALL
        SELECT 'type',n.nspname,t.typname,NULL,t.oid,a.grantor,a.grantee,a.privilege_type,a.is_grantable,false
        FROM pg_catalog.pg_type t JOIN pg_catalog.pg_namespace n ON n.oid=t.typnamespace
        CROSS JOIN LATERAL pg_catalog.aclexplode(COALESCE(t.typacl,pg_catalog.acldefault('T',t.typowner))) a
        WHERE n.nspname<>'public' AND n.nspname !~ '^pg_temp_' AND n.nspname !~ '^pg_toast_temp_'
        UNION ALL
        SELECT 'language','pg_catalog',l.lanname,NULL,l.oid,a.grantor,a.grantee,a.privilege_type,a.is_grantable,false
        FROM pg_catalog.pg_language l CROSS JOIN LATERAL
          pg_catalog.aclexplode(COALESCE(l.lanacl,pg_catalog.acldefault('l',l.lanowner))) a
        WHERE l.lanpltrusted
    """, (owner,))
    if not rows:
        raise SafetyError("Platform ACL metadata is incomplete.")
    validate_platform_acl(rows, ids, owner)
    params = query(connection, """
        SELECT 1 FROM pg_catalog.pg_parameter_acl p
        CROSS JOIN LATERAL pg_catalog.aclexplode(p.paracl) a
        WHERE a.grantee=0 OR a.grantee=ANY(%s)
    """, (ids,))
    if params:
        raise SafetyError("Unexpected PUBLIC or role-specific configuration privilege.")
