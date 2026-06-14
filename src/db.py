from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from sqlalchemy import Boolean, DateTime, Integer, String, create_engine, text
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

_DB_PATH = Path(__file__).parent.parent / "data" / "message_log.db"
_DB_PATH.parent.mkdir(parents=True, exist_ok=True)

_engine = create_engine(f"sqlite:///{_DB_PATH}", connect_args={"check_same_thread": False})


class Base(DeclarativeBase):
    pass


class ProcessedMessage(Base):
    __tablename__ = "processed_messages"

    mid: Mapped[str] = mapped_column(String, primary_key=True)
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class ConversationLog(Base):
    __tablename__ = "conversation_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    channel: Mapped[str] = mapped_column(String)
    sender_id_hash: Mapped[str] = mapped_column(String)
    message_text: Mapped[str] = mapped_column(String)
    response_text: Mapped[str] = mapped_column(String)
    latency_ms: Mapped[int] = mapped_column(Integer)
    escalated: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


def init_db() -> None:
    Base.metadata.create_all(_engine)
    # create_all skips indexes on tables that already exist, so add them
    # explicitly for databases created before these indexes were defined
    with _engine.connect() as conn:
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_processed_messages_processed_at "
                "ON processed_messages (processed_at)"
            )
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_conversation_log_created_at "
                "ON conversation_log (created_at)"
            )
        )
        conn.commit()


@contextmanager
def get_session():
    with Session(_engine) as session:
        yield session
        session.commit()
