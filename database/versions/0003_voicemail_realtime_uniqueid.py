"""Add Asterisk realtime uniqueid to voicemail users."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("voicemail")}
    if "uniqueid" not in columns:
        op.add_column("voicemail", sa.Column("uniqueid", sa.Integer(), nullable=True))
        op.execute(
            """
            UPDATE voicemail
            SET uniqueid = numbered.row_number
            FROM (
                SELECT context, mailbox, row_number() OVER () AS row_number
                FROM voicemail
            ) AS numbered
            WHERE voicemail.context = numbered.context
              AND voicemail.mailbox = numbered.mailbox
            """
        )
        op.execute("CREATE SEQUENCE IF NOT EXISTS voicemail_uniqueid_seq OWNED BY voicemail.uniqueid")
        op.execute("SELECT setval('voicemail_uniqueid_seq', COALESCE((SELECT max(uniqueid) FROM voicemail), 0) + 1, false)")
        op.alter_column("voicemail", "uniqueid", server_default=sa.text("nextval('voicemail_uniqueid_seq')"))
        op.alter_column("voicemail", "uniqueid", nullable=False)
        op.drop_constraint("voicemail_pkey", "voicemail", type_="primary")
        op.create_primary_key("voicemail_pkey", "voicemail", ["uniqueid"])
        op.create_unique_constraint("voicemail_context_mailbox_key", "voicemail", ["context", "mailbox"])
    indexes = {index["name"] for index in inspector.get_indexes("voicemail")}
    if "voicemail_context_mailbox_idx" not in indexes:
        op.create_index("voicemail_context_mailbox_idx", "voicemail", ["context", "mailbox"])
    op.execute("INSERT INTO kubevoip_schema_migrations(version) VALUES (4) ON CONFLICT (version) DO NOTHING")


def downgrade() -> None:
    raise NotImplementedError("KubeVoIP alpha database downgrades are not supported")
