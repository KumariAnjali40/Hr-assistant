import asyncio

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

import app.models  # noqa: F401  (register tables)
from app.config import settings
from app.db import Base

target_metadata = Base.metadata


def _run(connection):
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


async def _main():
    engine = create_async_engine(settings.database_url)
    async with engine.connect() as conn:
        await conn.run_sync(_run)
    await engine.dispose()


asyncio.run(_main())
