"""Tests for user sensor state attributes."""
from datetime import date
from types import SimpleNamespace

from custom_components.timebutler.api import Absence, User
from custom_components.timebutler.coordinator import UserStatus
from custom_components.timebutler.sensor import TimebutlerUserSensor


def _sensor(absence: Absence | None) -> TimebutlerUserSensor:
    """Return a user sensor backed by a stub coordinator, without HA setup."""
    user = User(
        id="1",
        last_name="Doe",
        first_name="John",
        email="john.doe@example.com",
        department="Engineering",
        branch_office="HQ",
        user_type="Admin",
        is_locked=False,
    )
    status = UserStatus(
        user=user,
        status=absence.absence_type if absence else "off",
        timeclock=None,
        current_absence=absence,
    )
    sensor = TimebutlerUserSensor.__new__(TimebutlerUserSensor)
    sensor._user_id = "1"
    sensor.coordinator = SimpleNamespace(
        data=SimpleNamespace(user_statuses={"1": status})
    )
    return sensor


def _absence(half_day: bool, morning: bool) -> Absence:
    today = date.today()
    return Absence(
        id="abs1",
        user_id="1",
        absence_type="vacation",
        start_date=today,
        end_date=today,
        state="Approved",
        half_day=half_day,
        morning=morning,
    )


def test_attributes_expose_half_day_morning_absence():
    attrs = _sensor(_absence(half_day=True, morning=True)).extra_state_attributes

    assert attrs["absence_half_day"] is True
    assert attrs["absence_morning"] is True


def test_attributes_expose_full_day_absence():
    attrs = _sensor(_absence(half_day=False, morning=False)).extra_state_attributes

    assert attrs["absence_half_day"] is False
    assert attrs["absence_morning"] is False


def test_attributes_omit_half_day_without_absence():
    attrs = _sensor(None).extra_state_attributes

    assert "absence_half_day" not in attrs
    assert "absence_morning" not in attrs
