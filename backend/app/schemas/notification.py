from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


NotificationType = Literal["weather", "bloom", "pollinator", "alert", "info"]


class NotificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    type: NotificationType
    title: str
    message: str
    created_at: datetime
    read: bool
    farm_id: UUID | None = None


class NotificationStatus(BaseModel):
    success: bool = True
    id: UUID
    read: bool
