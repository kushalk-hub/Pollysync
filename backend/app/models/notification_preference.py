from datetime import datetime
import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class NotificationPreference(Base):
    __tablename__ = "notification_preferences"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, unique=True)
    push_critical: Mapped[bool] = mapped_column(Boolean, default=True)
    push_daily: Mapped[bool] = mapped_column(Boolean, default=True)
    push_system: Mapped[bool] = mapped_column(Boolean, default=True)
    email_weekly: Mapped[bool] = mapped_column(Boolean, default=False)
    email_billing: Mapped[bool] = mapped_column(Boolean, default=False)
    whatsapp_urgent: Mapped[bool] = mapped_column(Boolean, default=False)
    sms_alerts: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
