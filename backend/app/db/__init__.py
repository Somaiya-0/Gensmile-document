"""Database package."""

from app.db.session import engine, async_session_factory
from app.db.init_db import create_database_tables

# Export AsyncSessionLocal for compatibility with existing code
AsyncSessionLocal = async_session_factory

async def get_db():
    """
    Dependency to get database session.
    Usage: async def endpoint(db: AsyncSession = Depends(get_db))
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

__all__ = [
    "engine",
    "async_session_factory",
    "AsyncSessionLocal", 
    "create_database_tables",
    "get_db",
]