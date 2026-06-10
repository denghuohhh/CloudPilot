from datetime import datetime
from typing import Optional
from sqlmodel import Field, SQLModel
class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True)
    password_hash: str
    is_admin: bool = False
    disabled: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
class Setting(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    owner_id: int = Field(index=True)
    key: str = Field(index=True)
    value: str = ''
class CloudSearchHistory(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    owner_id: int = Field(index=True)
    keyword: str
    result_count: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)
class CloudSaveTask(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    owner_id: int = Field(index=True)
    title: str
    disk_type: str
    share_url: str
    share_code: str = ''
    target_dir: str = ''
    status: str = 'pending'
    message: str = ''
    raw_json: str = ''
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
class CloudSubscription(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    owner_id: int = Field(index=True)
    keyword: str
    disk_type: str = 'all'
    include_words: str = ''
    exclude_words: str = ''
    target_dir: str = ''
    enabled: bool = True
    interval_minutes: int = 360
    last_run_at: Optional[datetime] = None
    last_message: str = ''
    created_at: datetime = Field(default_factory=datetime.utcnow)
