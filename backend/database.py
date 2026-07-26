from sqlmodel import SQLModel
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from .config import Config
from .complain_management.models import Complaint

engine = create_async_engine(
    Config.DATABASE_URL,
    echo=False
)

async_session_local = async_sessionmaker(
    engine,
    expire_on_commit=False
)

async def initdb():
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
        print("Tables Created if they did not exist")