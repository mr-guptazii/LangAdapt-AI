
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, UUIDPKMixin


class Language(Base, UUIDPKMixin, TimestampMixin):
    """A language supported either as a native or target language."""
    __tablename__ = "languages"

    code: Mapped[str] = mapped_column(String(8), unique=True, index=True)  # e.g. "en", "es", "fr"
    name: Mapped[str] = mapped_column(String(64))
    native_name: Mapped[str] = mapped_column(String(64))
    supports_learning_engine: Mapped[bool] = mapped_column(default=False)  # has a /learning/languages/<code> module


class Skill(Base, UUIDPKMixin, TimestampMixin):
    """A discrete, trackable curriculum skill (e.g. past_tense, articles)."""
    __tablename__ = "skills"

    language_code: Mapped[str] = mapped_column(String(8), index=True)
    code: Mapped[str] = mapped_column(String(64), index=True)  # e.g. "past_tense"
    name: Mapped[str] = mapped_column(String(128))
    category: Mapped[str] = mapped_column(String(32))  # grammar | vocabulary | pronunciation | fluency
    cefr_level: Mapped[str] = mapped_column(String(4))  # A1..C2
    description: Mapped[str | None] = mapped_column(String(500))

    __table_args__ = ({"sqlite_autoincrement": False},)
