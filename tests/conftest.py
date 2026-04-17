"""Shared test fixtures and mock data."""
from datetime import date
import pytest

from custom_components.timebutler.api import Absence, TimeclockStatus, User


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable loading of custom integrations in all tests."""
    yield

MOCK_TOKEN = "test_api_token_12345678"

USERS_CSV = (
    "User ID;Last name;First name;E-mail address;Department;Branch office;User type;User account locked\n"
    "1;Doe;John;john.doe@example.com;Engineering;HQ;Admin;false\n"
    "2;Smith;Jane;jane.smith@example.com;;HQ;Standard;false\n"
    "3;Locked;User;locked@example.com;Sales;HQ;Standard;true\n"
)

ABSENCES_CSV = (
    "ID;User ID;Type;From;To;State;Half a day;Morning\n"
    "1;1;vacation;01/04/2026;30/04/2026;Approved;false;false\n"
    "2;2;sickness;15/04/2026;16/04/2026;Done;false;false\n"
)

TIMECLOCK_RUNNING = "OK;RUNNING;1713340800000;0"
TIMECLOCK_IDLE = "OK;IDLE;0;0"
TIMECLOCK_PAUSED = "OK;PAUSED;1713340800000;1713344400000"


@pytest.fixture
def mock_user() -> User:
    return User(
        id="1",
        last_name="Doe",
        first_name="John",
        email="john.doe@example.com",
        department="Engineering",
        branch_office="HQ",
        user_type="Admin",
        is_locked=False,
    )


@pytest.fixture
def mock_user_2() -> User:
    return User(
        id="2",
        last_name="Smith",
        first_name="Jane",
        email="jane.smith@example.com",
        department="Marketing",
        branch_office="HQ",
        user_type="Standard",
        is_locked=False,
    )
