"""PostgreSQL persistence for Kamailio runtime data."""

import hashlib
from typing import Any

import psycopg
from psycopg.conninfo import make_conninfo

SCHEMA = """
CREATE TABLE IF NOT EXISTS version (
  id SERIAL PRIMARY KEY NOT NULL,
  table_name VARCHAR(32) NOT NULL UNIQUE,
  table_version INTEGER DEFAULT 0 NOT NULL
);
CREATE TABLE IF NOT EXISTS kubevoip_schema_migrations (
  version INTEGER PRIMARY KEY,
  applied_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);
CREATE TABLE IF NOT EXISTS subscriber (
  id SERIAL PRIMARY KEY NOT NULL,
  username VARCHAR(64) DEFAULT '' NOT NULL,
  domain VARCHAR(64) DEFAULT '' NOT NULL,
  password VARCHAR(64) DEFAULT '' NOT NULL,
  ha1 VARCHAR(128) DEFAULT '' NOT NULL,
  ha1b VARCHAR(128) DEFAULT '' NOT NULL,
  caller_id VARCHAR(128),
  owner_namespace VARCHAR(63) NOT NULL,
  owner_name VARCHAR(63) NOT NULL,
  UNIQUE (username, domain)
);
CREATE INDEX IF NOT EXISTS subscriber_owner_idx ON subscriber(owner_namespace, owner_name);
CREATE TABLE IF NOT EXISTS location (
  id SERIAL PRIMARY KEY NOT NULL,
  ruid VARCHAR(64) DEFAULT '' NOT NULL UNIQUE,
  username VARCHAR(64) DEFAULT '' NOT NULL,
  domain VARCHAR(64),
  contact VARCHAR(512) DEFAULT '' NOT NULL,
  received VARCHAR(128),
  path VARCHAR(512),
  expires TIMESTAMP WITHOUT TIME ZONE DEFAULT '2030-05-28 21:32:15' NOT NULL,
  q REAL DEFAULT 1.0 NOT NULL,
  callid VARCHAR(255) DEFAULT 'Default-Call-ID' NOT NULL,
  cseq INTEGER DEFAULT 1 NOT NULL,
  last_modified TIMESTAMP WITHOUT TIME ZONE DEFAULT '2000-01-01 00:00:01' NOT NULL,
  flags INTEGER DEFAULT 0 NOT NULL,
  cflags INTEGER DEFAULT 0 NOT NULL,
  user_agent VARCHAR(255) DEFAULT '' NOT NULL,
  socket VARCHAR(64),
  methods INTEGER,
  instance VARCHAR(255),
  reg_id INTEGER DEFAULT 0 NOT NULL,
  server_id INTEGER DEFAULT 0 NOT NULL,
  connection_id INTEGER DEFAULT 0 NOT NULL,
  keepalive INTEGER DEFAULT 0 NOT NULL,
  partition INTEGER DEFAULT 0 NOT NULL
);
CREATE INDEX IF NOT EXISTS location_account_contact_idx ON location(username, domain, contact);
CREATE INDEX IF NOT EXISTS location_expires_idx ON location(expires);
CREATE TABLE IF NOT EXISTS kubevoip_call_scope (
  namespace VARCHAR(63) NOT NULL,
  name VARCHAR(63) NOT NULL,
  gateway_name VARCHAR(63) NOT NULL,
  owner_uid VARCHAR(128) NOT NULL,
  PRIMARY KEY (namespace, name)
);
CREATE TABLE IF NOT EXISTS kubevoip_dial_policy (
  namespace VARCHAR(63) NOT NULL,
  name VARCHAR(63) NOT NULL,
  gateway_name VARCHAR(63) NOT NULL,
  owner_uid VARCHAR(128) NOT NULL,
  PRIMARY KEY (namespace, name)
);
CREATE TABLE IF NOT EXISTS kubevoip_dial_policy_scope (
  namespace VARCHAR(63) NOT NULL,
  policy_name VARCHAR(63) NOT NULL,
  scope_name VARCHAR(63) NOT NULL,
  position INTEGER NOT NULL,
  PRIMARY KEY (namespace, policy_name, scope_name)
);
CREATE INDEX IF NOT EXISTS kubevoip_dial_policy_scope_lookup_idx
  ON kubevoip_dial_policy_scope(namespace, policy_name, position);
CREATE TABLE IF NOT EXISTS kubevoip_sip_user (
  namespace VARCHAR(63) NOT NULL,
  name VARCHAR(63) NOT NULL,
  gateway_name VARCHAR(63) NOT NULL,
  extension VARCHAR(20) NOT NULL,
  auth_username VARCHAR(64) NOT NULL,
  caller_id VARCHAR(128),
  dial_policy_name VARCHAR(63) NOT NULL,
  owner_uid VARCHAR(128) NOT NULL,
  PRIMARY KEY (namespace, name),
  UNIQUE (namespace, gateway_name, extension),
  UNIQUE (namespace, gateway_name, auth_username)
);
CREATE INDEX IF NOT EXISTS kubevoip_sip_user_auth_idx
  ON kubevoip_sip_user(namespace, gateway_name, auth_username);
CREATE TABLE IF NOT EXISTS kubevoip_sip_trunk (
  namespace VARCHAR(63) NOT NULL,
  name VARCHAR(63) NOT NULL,
  gateway_name VARCHAR(63) NOT NULL,
  termination_uri VARCHAR(253) NOT NULL,
  inbound_dial_policy_name VARCHAR(63),
  outbound_caller_id VARCHAR(128),
  digest_username VARCHAR(128),
  digest_realm VARCHAR(253),
  digest_ha1 VARCHAR(128),
  owner_uid VARCHAR(128) NOT NULL,
  PRIMARY KEY (namespace, name)
);
CREATE TABLE IF NOT EXISTS kubevoip_sip_trunk_cidr (
  namespace VARCHAR(63) NOT NULL,
  trunk_name VARCHAR(63) NOT NULL,
  cidr CIDR NOT NULL,
  PRIMARY KEY (namespace, trunk_name, cidr)
);
CREATE TABLE IF NOT EXISTS kubevoip_call_route (
  namespace VARCHAR(63) NOT NULL,
  name VARCHAR(63) NOT NULL,
  gateway_name VARCHAR(63) NOT NULL,
  scope_name VARCHAR(63) NOT NULL,
  priority INTEGER NOT NULL,
  called_number VARCHAR(64) NOT NULL,
  target_kind VARCHAR(32) NOT NULL,
  target_ref VARCHAR(63) NOT NULL,
  target_extension VARCHAR(20),
  target_host VARCHAR(253),
  owner_uid VARCHAR(128) NOT NULL,
  PRIMARY KEY (namespace, name)
);
CREATE INDEX IF NOT EXISTS kubevoip_call_route_lookup_idx
  ON kubevoip_call_route(namespace, gateway_name, scope_name, priority, name);
INSERT INTO version(table_name, table_version) VALUES ('version', 1), ('subscriber', 7), ('location', 9)
ON CONFLICT (table_name) DO UPDATE SET table_version = EXCLUDED.table_version;
INSERT INTO kubevoip_schema_migrations(version) VALUES (1), (2)
ON CONFLICT (version) DO NOTHING;
"""


def connection_string(values: dict[str, str]) -> str:
    required = ("host", "port", "dbname", "user", "password")
    missing = [key for key in required if not values.get(key)]
    if missing:
        raise KeyError(f"database Secret missing keys: {', '.join(missing)}")
    return make_conninfo(**{key: values[key] for key in required})


def subscriber_ha1(username: str, domain: str, password: str) -> tuple[str, str]:
    ha1 = hashlib.md5(f"{username}:{domain}:{password}".encode(), usedforsecurity=False).hexdigest()
    ha1b = hashlib.md5(f"{username}@{domain}:{domain}:{password}".encode(), usedforsecurity=False).hexdigest()
    return ha1, ha1b


def trunk_digest_ha1(username: str, realm: str, password: str) -> str:
    return hashlib.md5(f"{username}:{realm}:{password}".encode(), usedforsecurity=False).hexdigest()


def _connect(database: dict[str, str]):
    return psycopg.connect(connection_string(database))


def ensure_schema(cursor) -> None:
    cursor.execute(SCHEMA)


def reconcile_call_scope(database: dict[str, str], namespace: str, name: str, uid: str, gateway_name: str) -> None:
    with _connect(database) as connection, connection.cursor() as cursor:
        ensure_schema(cursor)
        cursor.execute(
            """
            INSERT INTO kubevoip_call_scope(namespace, name, gateway_name, owner_uid)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (namespace, name) DO UPDATE SET
              gateway_name = EXCLUDED.gateway_name,
              owner_uid = EXCLUDED.owner_uid
            """,
            (namespace, name, gateway_name, uid),
        )


def delete_call_scope(database: dict[str, str], namespace: str, name: str) -> None:
    with _connect(database) as connection, connection.cursor() as cursor:
        cursor.execute("DELETE FROM kubevoip_call_scope WHERE namespace = %s AND name = %s", (namespace, name))


def reconcile_dial_policy(database: dict[str, str], namespace: str, name: str, uid: str, gateway_name: str, scopes: list[str]) -> None:
    with _connect(database) as connection, connection.cursor() as cursor:
        ensure_schema(cursor)
        cursor.execute(
            """
            INSERT INTO kubevoip_dial_policy(namespace, name, gateway_name, owner_uid)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (namespace, name) DO UPDATE SET
              gateway_name = EXCLUDED.gateway_name,
              owner_uid = EXCLUDED.owner_uid
            """,
            (namespace, name, gateway_name, uid),
        )
        cursor.execute("DELETE FROM kubevoip_dial_policy_scope WHERE namespace = %s AND policy_name = %s", (namespace, name))
        cursor.executemany(
            """
            INSERT INTO kubevoip_dial_policy_scope(namespace, policy_name, scope_name, position)
            VALUES (%s, %s, %s, %s)
            """,
            [(namespace, name, scope, position) for position, scope in enumerate(scopes)],
        )


def delete_dial_policy(database: dict[str, str], namespace: str, name: str) -> None:
    with _connect(database) as connection, connection.cursor() as cursor:
        cursor.execute("DELETE FROM kubevoip_dial_policy_scope WHERE namespace = %s AND policy_name = %s", (namespace, name))
        cursor.execute("DELETE FROM kubevoip_dial_policy WHERE namespace = %s AND name = %s", (namespace, name))


def reconcile_sip_user(
    database: dict[str, str],
    namespace: str,
    name: str,
    uid: str,
    username: str,
    domain: str,
    extension: str,
    dial_policy_name: str,
    password: str,
    caller_id: str | None,
) -> None:
    ha1, ha1b = subscriber_ha1(username, domain, password)
    with _connect(database) as connection, connection.cursor() as cursor:
        ensure_schema(cursor)
        cursor.execute(
            """
            INSERT INTO subscriber
              (username, domain, password, ha1, ha1b, caller_id, owner_namespace, owner_name)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (username, domain) DO UPDATE SET
              password = EXCLUDED.password,
              ha1 = EXCLUDED.ha1,
              ha1b = EXCLUDED.ha1b,
              caller_id = EXCLUDED.caller_id,
              owner_namespace = EXCLUDED.owner_namespace,
              owner_name = EXCLUDED.owner_name
            """,
            (username, domain, "", ha1, ha1b, caller_id, namespace, name),
        )
        cursor.execute(
            """
            INSERT INTO kubevoip_sip_user
              (namespace, name, gateway_name, extension, auth_username, caller_id, dial_policy_name, owner_uid)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (namespace, name) DO UPDATE SET
              gateway_name = EXCLUDED.gateway_name,
              extension = EXCLUDED.extension,
              auth_username = EXCLUDED.auth_username,
              caller_id = EXCLUDED.caller_id,
              dial_policy_name = EXCLUDED.dial_policy_name,
              owner_uid = EXCLUDED.owner_uid
            """,
            (namespace, name, domain, extension, username, caller_id, dial_policy_name, uid),
        )


def delete_sip_user(database: dict[str, str], namespace: str, name: str) -> None:
    with _connect(database) as connection, connection.cursor() as cursor:
        cursor.execute("DELETE FROM kubevoip_sip_user WHERE namespace = %s AND name = %s", (namespace, name))
        cursor.execute("DELETE FROM subscriber WHERE owner_namespace = %s AND owner_name = %s", (namespace, name))


def reconcile_sip_trunk(
    database: dict[str, str],
    namespace: str,
    name: str,
    uid: str,
    gateway_name: str,
    termination_uri: str,
    allowed_source_cidrs: list[str],
    inbound_dial_policy_name: str | None,
    outbound_caller_id: str | None,
    digest_username: str | None,
    digest_realm: str | None,
    digest_ha1: str | None,
) -> None:
    with _connect(database) as connection, connection.cursor() as cursor:
        ensure_schema(cursor)
        cursor.execute(
            """
            INSERT INTO kubevoip_sip_trunk
              (namespace, name, gateway_name, termination_uri, inbound_dial_policy_name,
               outbound_caller_id, digest_username, digest_realm, digest_ha1, owner_uid)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (namespace, name) DO UPDATE SET
              gateway_name = EXCLUDED.gateway_name,
              termination_uri = EXCLUDED.termination_uri,
              inbound_dial_policy_name = EXCLUDED.inbound_dial_policy_name,
              outbound_caller_id = EXCLUDED.outbound_caller_id,
              digest_username = EXCLUDED.digest_username,
              digest_realm = EXCLUDED.digest_realm,
              digest_ha1 = EXCLUDED.digest_ha1,
              owner_uid = EXCLUDED.owner_uid
            """,
            (
                namespace,
                name,
                gateway_name,
                termination_uri,
                inbound_dial_policy_name,
                outbound_caller_id,
                digest_username,
                digest_realm,
                digest_ha1,
                uid,
            ),
        )
        cursor.execute("DELETE FROM kubevoip_sip_trunk_cidr WHERE namespace = %s AND trunk_name = %s", (namespace, name))
        cursor.executemany(
            """
            INSERT INTO kubevoip_sip_trunk_cidr(namespace, trunk_name, cidr)
            VALUES (%s, %s, %s)
            """,
            [(namespace, name, cidr) for cidr in allowed_source_cidrs],
        )


def delete_sip_trunk(database: dict[str, str], namespace: str, name: str) -> None:
    with _connect(database) as connection, connection.cursor() as cursor:
        cursor.execute("DELETE FROM kubevoip_sip_trunk_cidr WHERE namespace = %s AND trunk_name = %s", (namespace, name))
        cursor.execute("DELETE FROM kubevoip_sip_trunk WHERE namespace = %s AND name = %s", (namespace, name))


def reconcile_call_route(
    database: dict[str, str],
    namespace: str,
    name: str,
    uid: str,
    gateway_name: str,
    scope_name: str,
    priority: int,
    called_number: str,
    target_kind: str,
    target_ref: str,
    target_extension: str | None,
    target_host: str | None,
) -> None:
    with _connect(database) as connection, connection.cursor() as cursor:
        ensure_schema(cursor)
        cursor.execute(
            """
            INSERT INTO kubevoip_call_route
              (namespace, name, gateway_name, scope_name, priority, called_number,
               target_kind, target_ref, target_extension, target_host, owner_uid)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (namespace, name) DO UPDATE SET
              gateway_name = EXCLUDED.gateway_name,
              scope_name = EXCLUDED.scope_name,
              priority = EXCLUDED.priority,
              called_number = EXCLUDED.called_number,
              target_kind = EXCLUDED.target_kind,
              target_ref = EXCLUDED.target_ref,
              target_extension = EXCLUDED.target_extension,
              target_host = EXCLUDED.target_host,
              owner_uid = EXCLUDED.owner_uid
            """,
            (
                namespace,
                name,
                gateway_name,
                scope_name,
                priority,
                called_number,
                target_kind,
                target_ref,
                target_extension,
                target_host,
                uid,
            ),
        )


def delete_call_route(database: dict[str, str], namespace: str, name: str) -> None:
    with _connect(database) as connection, connection.cursor() as cursor:
        cursor.execute("DELETE FROM kubevoip_call_route WHERE namespace = %s AND name = %s", (namespace, name))


def database_ready(database: dict[str, str]) -> bool:
    with _connect(database) as connection, connection.cursor() as cursor:
        ensure_schema(cursor)
        cursor.execute("SELECT 1")
        return cursor.fetchone() == (1,)


def redact_database(values: dict[str, Any]) -> dict[str, Any]:
    return {key: "<redacted>" if key == "password" else value for key, value in values.items()}
