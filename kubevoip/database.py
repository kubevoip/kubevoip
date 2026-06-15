"""PostgreSQL persistence for Kamailio subscribers."""

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
INSERT INTO version(table_name, table_version) VALUES ('version', 1), ('subscriber', 7), ('location', 9)
ON CONFLICT (table_name) DO UPDATE SET table_version = EXCLUDED.table_version;
INSERT INTO kubevoip_schema_migrations(version) VALUES (1) ON CONFLICT (version) DO NOTHING;
"""


def connection_string(values: dict[str, str]) -> str:
    required = ("host", "port", "dbname", "user", "password")
    missing = [key for key in required if not values.get(key)]
    if missing:
        raise KeyError(f"database Secret missing keys: {', '.join(missing)}")
    return make_conninfo(**{key: values[key] for key in required})


def reconcile_sip_user(
    database: dict[str, str],
    namespace: str,
    name: str,
    username: str,
    domain: str,
    password: str,
    caller_id: str | None,
) -> None:
    ha1 = hashlib.md5(f"{username}:{domain}:{password}".encode(), usedforsecurity=False).hexdigest()
    ha1b = hashlib.md5(f"{username}@{domain}:{domain}:{password}".encode(), usedforsecurity=False).hexdigest()
    with psycopg.connect(connection_string(database)) as connection, connection.cursor() as cursor:
        cursor.execute(SCHEMA)
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


def delete_sip_user(database: dict[str, str], namespace: str, name: str) -> None:
    with psycopg.connect(connection_string(database)) as connection, connection.cursor() as cursor:
        cursor.execute("DELETE FROM subscriber WHERE owner_namespace = %s AND owner_name = %s", (namespace, name))


def database_ready(database: dict[str, str]) -> bool:
    with psycopg.connect(connection_string(database)) as connection, connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        return cursor.fetchone() == (1,)


def redact_database(values: dict[str, Any]) -> dict[str, Any]:
    return {key: "<redacted>" if key == "password" else value for key, value in values.items()}
