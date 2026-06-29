"""Add PostgreSQL-backed Asterisk voicemail tables."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    existing_tables = set(inspect(op.get_bind()).get_table_names())
    if "voicemail" not in existing_tables:
        op.create_table(
            "voicemail",
            sa.Column("context", sa.String(length=80), primary_key=True, nullable=False),
            sa.Column("mailbox", sa.String(length=80), primary_key=True, nullable=False),
            sa.Column("password", sa.String(length=80), nullable=False),
            sa.Column("fullname", sa.String(length=80)),
            sa.Column("email", sa.String(length=80)),
            sa.Column("pager", sa.String(length=80)),
            sa.Column("options", sa.String(length=160)),
        )
    if "voicemessages" not in existing_tables:
        op.create_table(
            "voicemessages",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("msgnum", sa.Integer(), nullable=False),
            sa.Column("dir", sa.String(length=255), nullable=False),
            sa.Column("context", sa.String(length=80), nullable=False),
            sa.Column("macrocontext", sa.String(length=80)),
            sa.Column("callerid", sa.String(length=255)),
            sa.Column("origtime", sa.String(length=40)),
            sa.Column("duration", sa.String(length=20)),
            sa.Column("recording", sa.LargeBinary()),
            sa.Column("flag", sa.String(length=30)),
            sa.Column("mailboxuser", sa.String(length=80)),
            sa.Column("mailboxcontext", sa.String(length=80)),
        )
    existing_indexes = {index["name"] for index in inspect(op.get_bind()).get_indexes("voicemessages")} if "voicemessages" in set(inspect(op.get_bind()).get_table_names()) else set()
    if "voicemessages_mailbox_idx" not in existing_indexes:
        op.create_index("voicemessages_mailbox_idx", "voicemessages", ["mailboxuser", "mailboxcontext", "dir", "msgnum"])
    existing_tables = set(inspect(op.get_bind()).get_table_names())
    if "kubevoip_voicemail_mailbox" not in existing_tables:
        op.create_table(
            "kubevoip_voicemail_mailbox",
            sa.Column("namespace", sa.String(length=63), primary_key=True, nullable=False),
            sa.Column("name", sa.String(length=63), primary_key=True, nullable=False),
            sa.Column("gateway_name", sa.String(length=63), nullable=False),
            sa.Column("sip_user_name", sa.String(length=63), nullable=False),
            sa.Column("sip_auth_username", sa.String(length=64), nullable=False),
            sa.Column("sip_extension", sa.String(length=20), nullable=False),
            sa.Column("asterisk_pool_name", sa.String(length=63), nullable=False),
            sa.Column("target_host", sa.String(length=253), nullable=False),
            sa.Column("target_extension", sa.String(length=20), nullable=False),
            sa.Column("mailbox", sa.String(length=20), nullable=False),
            sa.Column("fallback_enabled", sa.Integer(), nullable=False),
            sa.Column("fallback_timeout_seconds", sa.Integer(), nullable=False),
            sa.Column("fallback_on_busy", sa.Integer(), nullable=False),
            sa.Column("fallback_on_unavailable", sa.Integer(), nullable=False),
            sa.Column("fallback_on_no_answer", sa.Integer(), nullable=False),
            sa.Column("email_enabled", sa.Integer(), nullable=False),
            sa.Column("email_to", sa.String(length=253)),
            sa.Column("email_from", sa.String(length=253)),
            sa.Column("email_provider", sa.String(length=32)),
            sa.Column("owner_uid", sa.String(length=128), nullable=False),
        )
    existing_indexes = {index["name"] for index in inspect(op.get_bind()).get_indexes("kubevoip_voicemail_mailbox")}
    if "kubevoip_voicemail_user_lookup_idx" not in existing_indexes:
        op.create_index(
            "kubevoip_voicemail_user_lookup_idx",
            "kubevoip_voicemail_mailbox",
            ["namespace", "gateway_name", "sip_user_name"],
        )
    op.execute("INSERT INTO kubevoip_schema_migrations(version) VALUES (3) ON CONFLICT (version) DO NOTHING")


def downgrade() -> None:
    raise NotImplementedError("KubeVoIP alpha database downgrades are not supported")
