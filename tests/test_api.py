"""Tests for the Timebutler API client parsing logic and error handling."""
import asyncio
from datetime import date
from unittest.mock import AsyncMock, patch

import aiohttp
import pytest
from aioresponses import aioresponses

from custom_components.timebutler.api import (
    TimebutlerApiClient,
    TimebutlerAuthError,
    TimebutlerConnectionError,
)
from custom_components.timebutler.const import API_BASE_URL, API_TIMEOUT

MOCK_TOKEN = "test_api_token"

USERS_CSV = (
    "User ID;Last name;First name;E-mail address;Department;Branch office;User type;User account locked\n"
    "1;Doe;John;john.doe@example.com;Engineering;HQ;Admin;false\n"
    "2;Smith;Jane;jane.smith@example.com;;HQ;Standard;false\n"
    "3;Locked;User;locked@example.com;Sales;HQ;Standard;true\n"
)

ABSENCES_CSV = (
    "ID;User ID;Type;From;To;State;Half a day;Morning\n"
    "1;1;vacation;01/04/2026;30/04/2026;Approved;false;false\n"
    "2;2;sickness;15/04/2026;16/04/2026;Done;true;false\n"
)

TIMECLOCK_RUNNING = "OK;RUNNING;1713340800000;0"
TIMECLOCK_IDLE = "OK;IDLE;0;0"
TIMECLOCK_PAUSED = "OK;PAUSED;1713340800000;1713344400000"


def _client() -> TimebutlerApiClient:
    return TimebutlerApiClient(MOCK_TOKEN)


# --- User parsing ---

async def test_get_users_filters_locked_users():
    client = _client()
    with patch.object(client, "_request", AsyncMock(return_value=USERS_CSV)):
        users = await client.async_get_users()

    assert len(users) == 2
    assert all(u.id != "3" for u in users)


async def test_get_users_parses_name_correctly():
    client = _client()
    with patch.object(client, "_request", AsyncMock(return_value=USERS_CSV)):
        users = await client.async_get_users()

    john = next(u for u in users if u.id == "1")
    assert john.name == "John Doe"
    assert john.email == "john.doe@example.com"
    assert john.department == "Engineering"


async def test_get_users_handles_empty_department():
    client = _client()
    with patch.object(client, "_request", AsyncMock(return_value=USERS_CSV)):
        users = await client.async_get_users()

    jane = next(u for u in users if u.id == "2")
    assert jane.department is None


# --- Absence parsing ---

async def test_get_absences_parses_type_and_dates():
    client = _client()
    with patch.object(client, "_request", AsyncMock(return_value=ABSENCES_CSV)):
        absences = await client.async_get_absences()

    vac = next(a for a in absences if a.id == "1")
    assert vac.absence_type == "vacation"
    assert vac.start_date == date(2026, 4, 1)
    assert vac.end_date == date(2026, 4, 30)
    assert vac.state == "Approved"
    assert vac.half_day is False


async def test_get_absences_parses_half_day_flag():
    client = _client()
    with patch.object(client, "_request", AsyncMock(return_value=ABSENCES_CSV)):
        absences = await client.async_get_absences()

    sick = next(a for a in absences if a.id == "2")
    assert sick.half_day is True


# --- Timeclock parsing ---

async def test_timeclock_running_state():
    client = _client()
    with patch.object(client, "_request", AsyncMock(return_value=TIMECLOCK_RUNNING)):
        status = await client.async_get_timeclock_status("1")

    assert status.is_working is True
    assert status.is_paused is False
    assert status.start_time is not None


async def test_timeclock_idle_state():
    client = _client()
    with patch.object(client, "_request", AsyncMock(return_value=TIMECLOCK_IDLE)):
        status = await client.async_get_timeclock_status("1")

    assert status.is_idle is True
    assert status.is_working is False
    assert status.start_time is None


async def test_timeclock_paused_state():
    client = _client()
    with patch.object(client, "_request", AsyncMock(return_value=TIMECLOCK_PAUSED)):
        status = await client.async_get_timeclock_status("1")

    assert status.is_paused is True
    assert status.pause_time is not None


# --- HTTP error handling ---

async def test_401_response_raises_auth_error():
    async with aiohttp.ClientSession() as session:
        client = TimebutlerApiClient(MOCK_TOKEN, session)
        with aioresponses() as mock:
            mock.post(
                f"{API_BASE_URL}/users?auth={MOCK_TOKEN}",
                body="Unauthorized",
                status=401,
            )
            with pytest.raises(TimebutlerAuthError):
                await client.async_get_users()


async def test_connection_error_raises_connection_error():
    async with aiohttp.ClientSession() as session:
        client = TimebutlerApiClient(MOCK_TOKEN, session)
        with aioresponses() as mock:
            mock.post(
                f"{API_BASE_URL}/users?auth={MOCK_TOKEN}",
                exception=aiohttp.ClientConnectionError("refused"),
            )
            with pytest.raises(TimebutlerConnectionError):
                await client.async_get_users()


# --- Token validation ---

async def test_validate_token_returns_true_on_success():
    client = _client()
    with patch.object(client, "_request", AsyncMock(return_value=USERS_CSV)):
        result = await client.async_validate_token()

    assert result is True


async def test_validate_token_returns_false_on_auth_error():
    client = _client()
    with patch.object(
        client, "_request", AsyncMock(side_effect=TimebutlerAuthError("invalid"))
    ):
        result = await client.async_validate_token()

    assert result is False
