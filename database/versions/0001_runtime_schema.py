"""Create KubeVoIP runtime schema."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "version",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("table_name", sa.String(length=32), nullable=False, unique=True),
        sa.Column("table_version", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_table(
        "kubevoip_schema_migrations",
        sa.Column("version", sa.Integer(), primary_key=True),
        sa.Column("applied_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_table(
        "subscriber",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("domain", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("password", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("ha1", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("ha1b", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("caller_id", sa.String(length=128)),
        sa.Column("owner_namespace", sa.String(length=63), nullable=False),
        sa.Column("owner_name", sa.String(length=63), nullable=False),
        sa.UniqueConstraint("username", "domain"),
    )
    op.create_index("subscriber_owner_idx", "subscriber", ["owner_namespace", "owner_name"])
    op.create_table(
        "location",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("ruid", sa.String(length=64), nullable=False, server_default="", unique=True),
        sa.Column("username", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("domain", sa.String(length=64)),
        sa.Column("contact", sa.String(length=512), nullable=False, server_default=""),
        sa.Column("received", sa.String(length=128)),
        sa.Column("path", sa.String(length=512)),
        sa.Column("expires", sa.TIMESTAMP(timezone=False), nullable=False, server_default="2030-05-28 21:32:15"),
        sa.Column("q", sa.REAL(), nullable=False, server_default="1.0"),
        sa.Column("callid", sa.String(length=255), nullable=False, server_default="Default-Call-ID"),
        sa.Column("cseq", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("last_modified", sa.TIMESTAMP(timezone=False), nullable=False, server_default="2000-01-01 00:00:01"),
        sa.Column("flags", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cflags", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("user_agent", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("socket", sa.String(length=64)),
        sa.Column("methods", sa.Integer()),
        sa.Column("instance", sa.String(length=255)),
        sa.Column("reg_id", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("server_id", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("connection_id", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("keepalive", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("partition", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("location_account_contact_idx", "location", ["username", "domain", "contact"])
    op.create_index("location_expires_idx", "location", ["expires"])
    op.create_table(
        "kubevoip_call_scope",
        sa.Column("namespace", sa.String(length=63), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=63), primary_key=True, nullable=False),
        sa.Column("gateway_name", sa.String(length=63), nullable=False),
        sa.Column("owner_uid", sa.String(length=128), nullable=False),
    )
    op.create_table(
        "kubevoip_dial_policy",
        sa.Column("namespace", sa.String(length=63), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=63), primary_key=True, nullable=False),
        sa.Column("gateway_name", sa.String(length=63), nullable=False),
        sa.Column("owner_uid", sa.String(length=128), nullable=False),
    )
    op.create_table(
        "kubevoip_dial_policy_scope",
        sa.Column("namespace", sa.String(length=63), primary_key=True, nullable=False),
        sa.Column("policy_name", sa.String(length=63), primary_key=True, nullable=False),
        sa.Column("scope_name", sa.String(length=63), primary_key=True, nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
    )
    op.create_index("kubevoip_dial_policy_scope_lookup_idx", "kubevoip_dial_policy_scope", ["namespace", "policy_name", "position"])
    op.create_table(
        "kubevoip_sip_user",
        sa.Column("namespace", sa.String(length=63), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=63), primary_key=True, nullable=False),
        sa.Column("gateway_name", sa.String(length=63), nullable=False),
        sa.Column("extension", sa.String(length=20), nullable=False),
        sa.Column("auth_username", sa.String(length=64), nullable=False),
        sa.Column("caller_id", sa.String(length=128)),
        sa.Column("dial_policy_name", sa.String(length=63), nullable=False),
        sa.Column("owner_uid", sa.String(length=128), nullable=False),
        sa.UniqueConstraint("namespace", "gateway_name", "extension"),
        sa.UniqueConstraint("namespace", "gateway_name", "auth_username"),
    )
    op.create_index("kubevoip_sip_user_auth_idx", "kubevoip_sip_user", ["namespace", "gateway_name", "auth_username"])
    op.create_table(
        "kubevoip_sip_trunk",
        sa.Column("namespace", sa.String(length=63), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=63), primary_key=True, nullable=False),
        sa.Column("gateway_name", sa.String(length=63), nullable=False),
        sa.Column("termination_uri", sa.String(length=253), nullable=False),
        sa.Column("inbound_dial_policy_name", sa.String(length=63)),
        sa.Column("outbound_caller_id", sa.String(length=128)),
        sa.Column("digest_username", sa.String(length=128)),
        sa.Column("digest_realm", sa.String(length=253)),
        sa.Column("digest_ha1", sa.String(length=128)),
        sa.Column("owner_uid", sa.String(length=128), nullable=False),
    )
    op.create_table(
        "kubevoip_sip_trunk_cidr",
        sa.Column("namespace", sa.String(length=63), primary_key=True, nullable=False),
        sa.Column("trunk_name", sa.String(length=63), primary_key=True, nullable=False),
        sa.Column("cidr", postgresql.CIDR(), primary_key=True, nullable=False),
    )
    op.create_table(
        "kubevoip_call_route",
        sa.Column("namespace", sa.String(length=63), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=63), primary_key=True, nullable=False),
        sa.Column("gateway_name", sa.String(length=63), nullable=False),
        sa.Column("scope_name", sa.String(length=63), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("called_number", sa.String(length=64), nullable=False),
        sa.Column("target_kind", sa.String(length=32), nullable=False),
        sa.Column("target_ref", sa.String(length=63), nullable=False),
        sa.Column("target_extension", sa.String(length=20)),
        sa.Column("target_host", sa.String(length=253)),
        sa.Column("owner_uid", sa.String(length=128), nullable=False),
    )
    op.create_index("kubevoip_call_route_lookup_idx", "kubevoip_call_route", ["namespace", "gateway_name", "scope_name", "priority", "name"])
    op.execute(
        """
        INSERT INTO version(table_name, table_version) VALUES ('version', 1), ('subscriber', 7), ('location', 9)
        ON CONFLICT (table_name) DO UPDATE SET table_version = EXCLUDED.table_version
        """
    )
    op.execute("INSERT INTO kubevoip_schema_migrations(version) VALUES (1), (2) ON CONFLICT (version) DO NOTHING")


def downgrade() -> None:
    raise NotImplementedError("KubeVoIP alpha database downgrades are not supported")
