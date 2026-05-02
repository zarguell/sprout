from datetime import datetime

from pydantic import BaseModel, ConfigDict


# --- Auth ---

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# --- Users ---

class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    display_name: str | None
    created_at: datetime


class UserUpdate(BaseModel):
    display_name: str | None = None
    password: str | None = None


# --- Plants ---

class PlantCreate(BaseModel):
    name: str
    species: str | None = None
    location: str | None = None
    notes: str | None = None


class PlantUpdate(BaseModel):
    name: str | None = None
    species: str | None = None
    location: str | None = None
    notes: str | None = None


class PlantRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    species: str | None
    location: str | None
    notes: str | None
    primary_photo_id: int | None
    archived: bool
    archived_at: datetime | None
    archived_by: int | None
    archive_reason: str | None
    created_by: int
    created_at: datetime
    updated_at: datetime | None


class PlantArchive(BaseModel):
    reason: str | None = None


class PlantDetail(PlantRead):
    tasks: list["TaskRead"] = []
    photos: list["PhotoRead"] = []
    activity: list["ActivityRead"] = []


# --- Tasks ---

class TaskCreate(BaseModel):
    type: str
    label: str | None = None
    interval_days: int | None = None
    due_date: datetime
    notes: str | None = None


class TaskUpdate(BaseModel):
    interval_days: int | None = None
    due_date: datetime | None = None
    label: str | None = None
    notes: str | None = None


class TaskComplete(BaseModel):
    notes: str | None = None
    advance: bool = True
    next_due_date: datetime | None = None


class TaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    plant_id: int
    type: str | None
    label: str | None
    interval_days: int | None
    due_date: datetime
    last_completed_at: datetime | None
    last_completed_by: int | None
    is_active: bool
    created_by: int
    notes: str | None
    created_at: datetime
    updated_at: datetime | None


# --- Photos ---

class PhotoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    plant_id: int
    original_url: str
    thumbnail_url: str
    uploaded_by: str
    uploaded_at: datetime
    caption: str | None
    is_primary: bool


# --- Activity ---

class ActivityCreate(BaseModel):
    content: str


class ActivityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    plant_id: int
    user_id: int
    username: str
    display_name: str
    content: str
    created_at: datetime


# --- Tasks Due ---

class TaskDueRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    task_id: int
    plant_id: int
    plant_name: str
    location: str | None
    type: str | None
    label: str | None
    due_date: datetime
    days_overdue: int
