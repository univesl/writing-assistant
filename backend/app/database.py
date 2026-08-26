import os

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, DeclarativeBase

DB_URL = os.getenv("DATABASE_URL", "sqlite:///./writing_assistant.db")

_is_sqlite = DB_URL.startswith("sqlite")
_connect_args = {
    "check_same_thread": False,
    "timeout": 30,
} if _is_sqlite else {}

engine = create_engine(
    DB_URL,
    connect_args=_connect_args,
    pool_pre_ping=True,
)

# 启用SQLite外键约束
@event.listens_for(engine, "connect")
def _sqlite_pragmas_on_connect(dbapi_con, _connection_record):
    if not _is_sqlite:
        return

    cursor = dbapi_con.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=30000")
        # WAL 允许生成流和另一个会话的保存请求同时进行，避免 SQLite 的
        # 默认 journal 模式把短暂写入冲突放大成“数据库被锁定”。
        if DB_URL != "sqlite:///:memory:":
            cursor.execute("PRAGMA journal_mode=WAL")
    finally:
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
