"""initial schema (later changes: `alembic revision --autogenerate -m "..."`)"""
from alembic import op

import app.models  # noqa: F401
from app.db import Base

revision = "0001"
down_revision = None


def upgrade():
    Base.metadata.create_all(bind=op.get_bind())


def downgrade():
    Base.metadata.drop_all(bind=op.get_bind())
