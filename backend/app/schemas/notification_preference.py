from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class NotificationPreferenceUpdate(BaseModel):
    push_critical: bool | None = None
    push_daily: bool | None = None
    push_system: bool | None = None
    email_weekly: bool | None = None
    email_billing: bool | None = None
    whatsapp_urgent: bool | None = None
    sms_alerts: bool | None = None


class NotificationPreferenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    push_critical: bool = True
    push_daily: bool = True
    push_system: bool = True
    email_weekly: bool = False
    email_billing: bool = False
    whatsapp_urgent: bool = False
    sms_alerts: bool = False
    created_at: datetime
    updated_at: datetime
