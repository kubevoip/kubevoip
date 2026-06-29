"""Add Asterisk voicemail message id."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("voicemessages")}
    if "msg_id" not in columns:
        op.add_column("voicemessages", sa.Column("msg_id", sa.String(length=40), nullable=True))
    op.execute("INSERT INTO kubevoip_schema_migrations(version) VALUES (5) ON CONFLICT (version) DO NOTHING")


def downgrade() -> None:
    raise NotImplementedError("KubeVoIP alpha database downgrades are not supported")
