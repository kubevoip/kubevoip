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

INSERT INTO kubevoip_schema_migrations(version) VALUES (2)
ON CONFLICT (version) DO NOTHING;
