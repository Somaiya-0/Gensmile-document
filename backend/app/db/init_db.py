from app.db.session import engine
from app.models import Base


async def create_database_tables() -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
