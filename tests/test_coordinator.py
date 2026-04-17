"""Tests for coordinator status computation logic."""
from datetime import date, timedelta

import pytest

from custom_components.timebutler.api import Absence, TimeclockStatus, User
from custom_components.timebutler.const import STATUS_OFF, STATUS_PAUSED, STATUS_WORKING
from custom_components.timebutler.coordinator import TimebutlerDataUpdateCoordinator


def _coordinator() -> TimebutlerDataUpdateCoordinator:
    """Return a coordinator instance without full HA setup for unit testing."""
    return TimebutlerDataUpdateCoordinator.__new__(TimebutlerDataUpdateCoordinator)


def _user(user_id: str, department: str | None = None) -> User:
    return User(
        id=user_id,
        last_name="Test",
        first_name="User",
        email=f"user{user_id}@test.com",
        department=department,
        branch_office=None,
        user_type="Standard",
        is_locked=False,
    )


def _timeclock(user_id: str, state: str) -> TimeclockStatus:
    return TimeclockStatus(user_id=user_id, state=state, start_time=None, pause_time=None)


def _absence(
    user_id: str,
    absence_type: str,
    state: str = "Approved",
    days_offset: int = 0,
) -> Absence:
    today = date.today() + timedelta(days=days_offset)
    return Absence(
        id="abs1",
        user_id=user_id,
        absence_type=absence_type,
        start_date=today,
        end_date=today,
        state=state,
        half_day=False,
        morning=False,
    )


def test_running_timeclock_gives_working_status():
    coordinator = _coordinator()
    users = {"1": _user("1")}
    timeclocks = {"1": _timeclock("1", "RUNNING")}

    result = coordinator._compute_user_statuses(users, [], timeclocks)

    assert result["1"].status == STATUS_WORKING


def test_paused_timeclock_gives_paused_status():
    coordinator = _coordinator()
    users = {"1": _user("1")}
    timeclocks = {"1": _timeclock("1", "PAUSED")}

    result = coordinator._compute_user_statuses(users, [], timeclocks)

    assert result["1"].status == STATUS_PAUSED


def test_idle_timeclock_no_absence_gives_off_status():
    coordinator = _coordinator()
    users = {"1": _user("1")}
    timeclocks = {"1": _timeclock("1", "IDLE")}

    result = coordinator._compute_user_statuses(users, [], timeclocks)

    assert result["1"].status == STATUS_OFF


def test_approved_absence_today_gives_absence_type_as_status():
    coordinator = _coordinator()
    users = {"1": _user("1")}
    timeclocks = {"1": _timeclock("1", "IDLE")}
    absences = [_absence("1", "vacation")]

    result = coordinator._compute_user_statuses(users, absences, timeclocks)

    assert result["1"].status == "vacation"


def test_timeclock_working_takes_priority_over_active_absence():
    coordinator = _coordinator()
    users = {"1": _user("1")}
    timeclocks = {"1": _timeclock("1", "RUNNING")}
    absences = [_absence("1", "vacation")]

    result = coordinator._compute_user_statuses(users, absences, timeclocks)

    assert result["1"].status == STATUS_WORKING


def test_pending_absence_does_not_affect_status():
    coordinator = _coordinator()
    users = {"1": _user("1")}
    timeclocks = {"1": _timeclock("1", "IDLE")}
    absences = [_absence("1", "vacation", state="Pending")]

    result = coordinator._compute_user_statuses(users, absences, timeclocks)

    assert result["1"].status == STATUS_OFF


def test_absence_type_with_spaces_is_slugified():
    coordinator = _coordinator()
    users = {"1": _user("1")}
    timeclocks = {"1": _timeclock("1", "IDLE")}
    absences = [_absence("1", "business trip")]

    result = coordinator._compute_user_statuses(users, absences, timeclocks)

    assert result["1"].status == "business_trip"


def test_future_absence_does_not_affect_current_status():
    coordinator = _coordinator()
    users = {"1": _user("1")}
    timeclocks = {"1": _timeclock("1", "IDLE")}
    absences = [_absence("1", "vacation", days_offset=1)]

    result = coordinator._compute_user_statuses(users, absences, timeclocks)

    assert result["1"].status == STATUS_OFF


def test_user_status_is_absent_when_absence_active():
    coordinator = _coordinator()
    users = {"1": _user("1")}
    timeclocks = {"1": _timeclock("1", "IDLE")}
    absences = [_absence("1", "vacation")]

    result = coordinator._compute_user_statuses(users, absences, timeclocks)

    assert result["1"].is_absent is True
    assert result["1"].current_absence is not None


def test_user_status_not_absent_when_no_absence():
    coordinator = _coordinator()
    users = {"1": _user("1")}
    timeclocks = {"1": _timeclock("1", "IDLE")}

    result = coordinator._compute_user_statuses(users, [], timeclocks)

    assert result["1"].is_absent is False
    assert result["1"].current_absence is None
