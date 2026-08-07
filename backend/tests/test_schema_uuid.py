"""Regression tests for Supabase UUID ids.

Supabase defines PK/FK columns as UUID, so psycopg2 returns Python ``uuid.UUID``
objects. Response schemas must accept those (while still coercing plain strings
from SQLite), otherwise every authenticated endpoint 500s on Render/Supabase.
"""
import uuid
from datetime import datetime, timezone

from app.api.routes.predictions import _prediction_to_read
from app.models.farm import Farm
from app.models.notification import Notification
from app.models.notification_preference import NotificationPreference
from app.models.prediction import Prediction
from app.models.team_member import TeamMember
from app.models.user import User
from app.schemas.farm import FarmRead
from app.schemas.notification import NotificationRead, NotificationStatus
from app.schemas.notification_preference import NotificationPreferenceRead
from app.schemas.prediction import PredictionRead
from app.schemas.team_member import TeamMemberRead
from app.schemas.user import AuthResponse, UserRead

UID = uuid.UUID("4d01c3a9-6a07-435c-868f-57f43350d865")
NOW = datetime.now(timezone.utc)


def _user(**overrides) -> User:
    defaults = dict(
        id=UID,
        email="farmer@example.com",
        full_name=None,
        oauth_provider="firebase",
        oauth_subject="fb-123",
        has_onboarded=False,
        created_at=NOW,
    )
    defaults.update(overrides)
    return User(**defaults)


def test_user_read_accepts_uuid_id_and_nullable_name():
    read = UserRead.model_validate(_user())
    assert isinstance(read.id, uuid.UUID)
    assert read.id == UID
    assert read.full_name is None
    assert read.model_dump(mode="json")["id"] == str(UID)


def test_user_read_coerces_legacy_string_id():
    read = UserRead.model_validate(_user(id=str(UID)))
    assert read.id == UID


def test_auth_response_serializes_uuid_user_id():
    response = AuthResponse(
        access_token="access-token",
        refresh_token="refresh-token",
        expires_in=1800,
        user=UserRead.model_validate(_user(full_name="A Farmer")),
    )
    assert response.user.id == UID


def test_farm_read_accepts_uuid_id():
    farm = Farm(id=UID, user_id=UID, name="North Field", crop_type="Cotton", created_at=NOW, updated_at=NOW)
    read = FarmRead(
        id=farm.id,
        name=farm.name,
        crop_type=farm.crop_type,
        crop=farm.crop_type,
        is_default=False,
        created_at=farm.created_at,
    )
    assert isinstance(read.id, uuid.UUID)
    assert read.id == UID


def test_prediction_read_accepts_uuid_ids():
    farm = Farm(id=UID, user_id=UID, name="North Field", crop_type="Cotton", created_at=NOW, updated_at=NOW)
    prediction = Prediction(
        id=UID,
        farm_id=UID,
        flowering_start="2026-01-01",
        flowering_end="2026-01-08",
        flowering_confidence=0.9,
        psi_score=70,
        risk_level="Low",
        ndvi_value=0.72,
        recommendation="Good conditions",
        created_at=NOW,
    )
    read = _prediction_to_read(prediction, farm)
    assert isinstance(read, PredictionRead)
    assert isinstance(read.id, uuid.UUID)
    assert isinstance(read.farm_id, uuid.UUID)
    assert read.weather_summary == {}
    assert read.bee_species == []


def test_notification_schemas_accept_uuid_ids():
    notification = Notification(
        id=UID,
        user_id=UID,
        farm_id=UID,
        type="info",
        title="Title",
        message="Message",
        read=False,
        created_at=NOW,
    )
    read = NotificationRead.model_validate(notification)
    assert isinstance(read.id, uuid.UUID)
    assert isinstance(read.farm_id, uuid.UUID)
    status = NotificationStatus(id=notification.id, read=True)
    assert status.id == UID


def test_notification_preference_read_accepts_uuid_ids():
    prefs = NotificationPreference(
        id=UID,
        user_id=UID,
        push_critical=True,
        push_daily=True,
        push_system=True,
        email_weekly=False,
        email_billing=False,
        whatsapp_urgent=False,
        sms_alerts=False,
        created_at=NOW,
        updated_at=NOW,
    )
    read = NotificationPreferenceRead.model_validate(prefs)
    assert isinstance(read.id, uuid.UUID)
    assert isinstance(read.user_id, uuid.UUID)


def test_team_member_read_accepts_uuid_ids():
    member = TeamMember(
        id=UID,
        farm_id=UID,
        invited_by=UID,
        email="member@example.com",
        name="Member",
        role="viewer",
        status="pending",
        created_at=NOW,
    )
    read = TeamMemberRead.model_validate(member)
    assert isinstance(read.id, uuid.UUID)
    assert isinstance(read.farm_id, uuid.UUID)
    assert isinstance(read.invited_by, uuid.UUID)
