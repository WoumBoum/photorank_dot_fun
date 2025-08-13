from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Float, DateTime, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql.expression import text
from sqlalchemy.sql.sqltypes import TIMESTAMP

from .database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, nullable=False)
    email = Column(String, nullable=False, unique=True)
    username = Column(String, nullable=False, unique=True)
    provider = Column(String, nullable=False)  # 'github' or 'google'
    provider_id = Column(String, nullable=False, unique=True)
    created_at = Column(TIMESTAMP(timezone=True),
                        nullable=False, server_default=text('now()'))


class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, nullable=False)
    name = Column(String, nullable=False, unique=True)
    description = Column(String, nullable=True)
    question = Column(Text, nullable=False)
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True),
                        nullable=False, server_default=text('now()'))


class Photo(Base):
    __tablename__ = "photos"

    id = Column(Integer, primary_key=True, nullable=False)
    filename = Column(String, nullable=False, unique=True)
    elo_rating = Column(Float, nullable=False, default=1200.0)
    total_duels = Column(Integer, nullable=False, default=0)
    wins = Column(Integer, nullable=False, default=0)
    created_at = Column(TIMESTAMP(timezone=True),
                        nullable=False, server_default=text('now()'))
    owner_id = Column(Integer, ForeignKey(
        "users.id", ondelete="CASCADE"), nullable=False)
    category_id = Column(Integer, ForeignKey(
        "categories.id", ondelete="CASCADE"), nullable=False)


class Vote(Base):
    __tablename__ = "votes"

    id = Column(Integer, primary_key=True, nullable=False)
    user_id = Column(Integer, ForeignKey(
        "users.id", ondelete="CASCADE"), nullable=False)
    winner_id = Column(Integer, ForeignKey(
        "photos.id", ondelete="CASCADE"), nullable=False)
    loser_id = Column(Integer, ForeignKey(
        "photos.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(TIMESTAMP(timezone=True),
                        nullable=False, server_default=text('now()'))


class UploadLimit(Base):
    __tablename__ = "upload_limits"

    user_id = Column(Integer, ForeignKey(
        "users.id", ondelete="CASCADE"), primary_key=True)
    upload_count = Column(Integer, nullable=False, default=0)
    last_upload_date = Column(DateTime, nullable=False, server_default=text('now()'))