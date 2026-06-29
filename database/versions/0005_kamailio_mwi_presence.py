"""Add Kamailio presence tables for MWI."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def _tables() -> set[str]:
    return set(inspect(op.get_bind()).get_table_names())


def _indexes(table: str) -> set[str]:
    return {index["name"] for index in inspect(op.get_bind()).get_indexes(table)}


def _version(table: str, version: int) -> None:
    op.execute(
        f"""
        INSERT INTO version(table_name, table_version) VALUES ('{table}', {version})
        ON CONFLICT (table_name) DO UPDATE SET table_version = EXCLUDED.table_version
        """
    )


def upgrade() -> None:
    existing = _tables()
    if "presentity" not in existing:
        op.create_table(
            "presentity",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("username", sa.String(length=64), nullable=False),
            sa.Column("domain", sa.String(length=64), nullable=False),
            sa.Column("event", sa.String(length=64), nullable=False),
            sa.Column("etag", sa.String(length=128), nullable=False),
            sa.Column("expires", sa.Integer(), nullable=False),
            sa.Column("received_time", sa.Integer(), nullable=False),
            sa.Column("body", sa.LargeBinary(), nullable=False),
            sa.Column("sender", sa.String(length=255), nullable=False),
            sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("ruid", sa.String(length=64)),
            sa.UniqueConstraint("username", "domain", "event", "etag", name="presentity_presentity_idx"),
            sa.UniqueConstraint("ruid", name="presentity_ruid_idx"),
        )
    indexes = _indexes("presentity")
    if "presentity_presentity_expires" not in indexes:
        op.create_index("presentity_presentity_expires", "presentity", ["expires"])
    if "presentity_account_idx" not in indexes:
        op.create_index("presentity_account_idx", "presentity", ["username", "domain", "event"])
    _version("presentity", 5)

    existing = _tables()
    if "active_watchers" not in existing:
        op.create_table(
            "active_watchers",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("presentity_uri", sa.String(length=255), nullable=False),
            sa.Column("watcher_username", sa.String(length=64), nullable=False),
            sa.Column("watcher_domain", sa.String(length=64), nullable=False),
            sa.Column("to_user", sa.String(length=64), nullable=False),
            sa.Column("to_domain", sa.String(length=64), nullable=False),
            sa.Column("event", sa.String(length=64), nullable=False, server_default="presence"),
            sa.Column("event_id", sa.String(length=64)),
            sa.Column("to_tag", sa.String(length=128), nullable=False),
            sa.Column("from_tag", sa.String(length=128), nullable=False),
            sa.Column("callid", sa.String(length=255), nullable=False),
            sa.Column("local_cseq", sa.Integer(), nullable=False),
            sa.Column("remote_cseq", sa.Integer(), nullable=False),
            sa.Column("contact", sa.String(length=255), nullable=False),
            sa.Column("record_route", sa.Text()),
            sa.Column("expires", sa.Integer(), nullable=False),
            sa.Column("status", sa.Integer(), nullable=False, server_default="2"),
            sa.Column("reason", sa.String(length=64)),
            sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("socket_info", sa.String(length=64), nullable=False),
            sa.Column("local_contact", sa.String(length=255), nullable=False),
            sa.Column("from_user", sa.String(length=64), nullable=False),
            sa.Column("from_domain", sa.String(length=64), nullable=False),
            sa.Column("updated", sa.Integer(), nullable=False),
            sa.Column("updated_winfo", sa.Integer(), nullable=False),
            sa.Column("flags", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("user_agent", sa.String(length=255), server_default=""),
            sa.UniqueConstraint("callid", "to_tag", "from_tag", name="active_watchers_active_watchers_idx"),
        )
    indexes = _indexes("active_watchers")
    if "active_watchers_active_watchers_expires" not in indexes:
        op.create_index("active_watchers_active_watchers_expires", "active_watchers", ["expires"])
    if "active_watchers_active_watchers_pres" not in indexes:
        op.create_index("active_watchers_active_watchers_pres", "active_watchers", ["presentity_uri", "event"])
    if "active_watchers_updated_idx" not in indexes:
        op.create_index("active_watchers_updated_idx", "active_watchers", ["updated"])
    if "active_watchers_updated_winfo_idx" not in indexes:
        op.create_index("active_watchers_updated_winfo_idx", "active_watchers", ["updated_winfo", "presentity_uri"])
    _version("active_watchers", 12)

    existing = _tables()
    if "watchers" not in existing:
        op.create_table(
            "watchers",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("presentity_uri", sa.String(length=255), nullable=False),
            sa.Column("watcher_username", sa.String(length=64), nullable=False),
            sa.Column("watcher_domain", sa.String(length=64), nullable=False),
            sa.Column("event", sa.String(length=64), nullable=False, server_default="presence"),
            sa.Column("status", sa.Integer(), nullable=False),
            sa.Column("reason", sa.String(length=64)),
            sa.Column("inserted_time", sa.Integer(), nullable=False),
            sa.UniqueConstraint("presentity_uri", "watcher_username", "watcher_domain", "event", name="watchers_watcher_idx"),
        )
    _version("watchers", 3)

    existing = _tables()
    if "xcap" not in existing:
        op.create_table(
            "xcap",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("username", sa.String(length=64), nullable=False),
            sa.Column("domain", sa.String(length=64), nullable=False),
            sa.Column("doc", sa.LargeBinary(), nullable=False),
            sa.Column("doc_type", sa.Integer(), nullable=False),
            sa.Column("etag", sa.String(length=128), nullable=False),
            sa.Column("source", sa.Integer(), nullable=False),
            sa.Column("doc_uri", sa.String(length=255), nullable=False),
            sa.Column("port", sa.Integer(), nullable=False),
            sa.UniqueConstraint("doc_uri", name="xcap_doc_uri_idx"),
        )
    indexes = _indexes("xcap")
    if "xcap_account_doc_type_idx" not in indexes:
        op.create_index("xcap_account_doc_type_idx", "xcap", ["username", "domain", "doc_type"])
    if "xcap_account_doc_type_uri_idx" not in indexes:
        op.create_index("xcap_account_doc_type_uri_idx", "xcap", ["username", "domain", "doc_type", "doc_uri"])
    if "xcap_account_doc_uri_idx" not in indexes:
        op.create_index("xcap_account_doc_uri_idx", "xcap", ["username", "domain", "doc_uri"])
    _version("xcap", 4)

    existing = _tables()
    if "pua" not in existing:
        op.create_table(
            "pua",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("pres_uri", sa.String(length=255), nullable=False),
            sa.Column("pres_id", sa.String(length=255), nullable=False),
            sa.Column("event", sa.Integer(), nullable=False),
            sa.Column("expires", sa.Integer(), nullable=False),
            sa.Column("desired_expires", sa.Integer(), nullable=False),
            sa.Column("flag", sa.Integer(), nullable=False),
            sa.Column("etag", sa.String(length=128), nullable=False),
            sa.Column("tuple_id", sa.String(length=64)),
            sa.Column("watcher_uri", sa.String(length=255), nullable=False),
            sa.Column("call_id", sa.String(length=255), nullable=False),
            sa.Column("to_tag", sa.String(length=128), nullable=False),
            sa.Column("from_tag", sa.String(length=128), nullable=False),
            sa.Column("cseq", sa.Integer(), nullable=False),
            sa.Column("record_route", sa.Text()),
            sa.Column("contact", sa.String(length=255), nullable=False),
            sa.Column("remote_contact", sa.String(length=255), nullable=False),
            sa.Column("version", sa.Integer(), nullable=False),
            sa.Column("extra_headers", sa.Text(), nullable=False),
            sa.UniqueConstraint("etag", "tuple_id", "call_id", "from_tag", name="pua_pua_idx"),
        )
    indexes = _indexes("pua")
    if "pua_expires_idx" not in indexes:
        op.create_index("pua_expires_idx", "pua", ["expires"])
    if "pua_dialog1_idx" not in indexes:
        op.create_index("pua_dialog1_idx", "pua", ["pres_id", "pres_uri"])
    if "pua_dialog2_idx" not in indexes:
        op.create_index("pua_dialog2_idx", "pua", ["call_id", "from_tag"])
    if "pua_record_idx" not in indexes:
        op.create_index("pua_record_idx", "pua", ["pres_id"])
    _version("pua", 7)

    op.execute("INSERT INTO kubevoip_schema_migrations(version) VALUES (6) ON CONFLICT (version) DO NOTHING")


def downgrade() -> None:
    raise NotImplementedError("KubeVoIP alpha database downgrades are not supported")
