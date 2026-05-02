from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    display_name: Mapped[str | None] = mapped_column(Text, default=None)
    hashed_password: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    revoked_tokens: Mapped[list["RevokedToken"]] = relationship(back_populates="revoked_by_user")
    plants_created: Mapped[list["Plant"]] = relationship(back_populates="created_by_user")
    tasks_created: Mapped[list["Task"]] = relationship(back_populates="created_by_user")
    tasks_completed: Mapped[list["Task"]] = relationship(back_populates="last_completed_by_user")
    photos_uploaded: Mapped[list["Photo"]] = relationship(back_populates="uploaded_by_user")
    activity_entries: Mapped[list["PlantActivity"]] = relationship(back_populates="user")


class RevokedToken(Base):
    __tablename__ = "revoked_tokens"

    jti: Mapped[str] = mapped_column(Text, primary_key=True)
    revoked_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    revoked_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))

    revoked_by_user: Mapped["User"] = relationship(back_populates="revoked_tokens")


class Photo(Base):
    __tablename__ = "photos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plant_id: Mapped[int] = mapped_column(Integer, ForeignKey("plants.id", ondelete="CASCADE"))
    original_path: Mapped[str] = mapped_column(Text, nullable=False)
    thumbnail_path: Mapped[str] = mapped_column(Text, nullable=False)
    uploaded_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    caption: Mapped[str | None] = mapped_column(Text, default=None)

    plant: Mapped["Plant"] = relationship(back_populates="photos")
    uploaded_by_user: Mapped["User"] = relationship(back_populates="photos_uploaded")


class Plant(Base):
    __tablename__ = "plants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    species: Mapped[str | None] = mapped_column(Text, default=None)
    location: Mapped[str | None] = mapped_column(Text, default=None)
    notes: Mapped[str | None] = mapped_column(Text, default=None)
    primary_photo_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("photos.id", ondelete="SET NULL"), default=None)
    archived: Mapped[bool] = mapped_column(Boolean, server_default=func.false())
    archived_at: Mapped[datetime | None] = mapped_column(DateTime, default=None)
    archived_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), default=None)
    archive_reason: Mapped[str | None] = mapped_column(Text, default=None)
    created_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    created_by_user: Mapped["User"] = relationship(back_populates="plants_created")
    archived_by_user: Mapped["User"] = relationship(foreign_keys=[archived_by])
    primary_photo: Mapped["Photo | None"] = relationship(foreign_keys=[primary_photo_id])
    tasks: Mapped[list["Task"]] = relationship(back_populates="plant", cascade="all, delete-orphan")
    photos: Mapped[list["Photo"]] = relationship(back_populates="plant", cascade="all, delete-orphan")
    activity: Mapped[list["PlantActivity"]] = relationship(back_populates="plant", cascade="all, delete-orphan")


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        CheckConstraint("type IN ('water', 'fertilize', 'repot', 'custom')", name="chk_task_type"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plant_id: Mapped[int] = mapped_column(Integer, ForeignKey("plants.id", ondelete="CASCADE"))
    type: Mapped[str | None] = mapped_column(Text, default=None)
    label: Mapped[str | None] = mapped_column(Text, default=None)
    interval_days: Mapped[int | None] = mapped_column(Integer, default=None)
    due_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    last_completed_at: Mapped[datetime | None] = mapped_column(DateTime, default=None)
    last_completed_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), default=None)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=func.true())
    created_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    notes: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    plant: Mapped["Plant"] = relationship(back_populates="tasks")
    created_by_user: Mapped["User"] = relationship(back_populates="tasks_created")
    last_completed_by_user: Mapped["User"] = relationship(back_populates="tasks_completed")


class PlantActivity(Base):
    __tablename__ = "plant_activity"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plant_id: Mapped[int] = mapped_column(Integer, ForeignKey("plants.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())

    plant: Mapped["Plant"] = relationship(back_populates="activity")
    user: Mapped["User"] = relationship(back_populates="activity_entries")
