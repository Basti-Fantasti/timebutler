"""Timebutler API client."""

from __future__ import annotations

import asyncio
import csv
import io
import logging
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

import aiohttp

from .const import (
    API_BASE_URL,
    API_TIMEOUT,
    TIMECLOCK_IDLE,
    TIMECLOCK_PAUSED,
    TIMECLOCK_RUNNING,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class User:
    """Timebutler user."""

    id: str
    last_name: str
    first_name: str
    email: str
    department: str | None
    branch_office: str | None
    user_type: str
    is_locked: bool

    @property
    def name(self) -> str:
        """Return full name."""
        return f"{self.first_name} {self.last_name}".strip()


@dataclass
class Absence:
    """Timebutler absence record."""

    id: str
    user_id: str
    absence_type: str
    start_date: date
    end_date: date
    state: str
    half_day: bool
    morning: bool


@dataclass
class TimeclockStatus:
    """Timebutler timeclock status."""

    user_id: str
    state: str  # IDLE, RUNNING, PAUSED
    start_time: datetime | None
    pause_time: datetime | None

    @property
    def is_working(self) -> bool:
        """Return True if user is currently working."""
        return self.state == TIMECLOCK_RUNNING

    @property
    def is_paused(self) -> bool:
        """Return True if user is on break."""
        return self.state == TIMECLOCK_PAUSED

    @property
    def is_idle(self) -> bool:
        """Return True if user is not clocked in."""
        return self.state == TIMECLOCK_IDLE


class TimebutlerApiError(Exception):
    """Base exception for Timebutler API errors."""


class TimebutlerAuthError(TimebutlerApiError):
    """Authentication error."""


class TimebutlerConnectionError(TimebutlerApiError):
    """Connection error."""


class TimebutlerApiClient:
    """Client for Timebutler API."""

    def __init__(
        self,
        api_token: str,
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        """Initialize the API client."""
        self._api_token = api_token
        self._session = session
        self._close_session = False

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None:
            self._session = aiohttp.ClientSession()
            self._close_session = True
        return self._session

    async def close(self) -> None:
        """Close the session if we created it."""
        if self._close_session and self._session:
            await self._session.close()
            self._session = None

    async def _request(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
    ) -> str:
        """Make API request."""
        session = await self._get_session()
        url = f"{API_BASE_URL}/{endpoint}"

        request_params = {"auth": self._api_token}
        if params:
            request_params.update(params)

        try:
            async with asyncio.timeout(API_TIMEOUT):
                async with session.post(url, params=request_params) as response:
                    text = await response.text()

                    if response.status == 401:
                        raise TimebutlerAuthError(
                            "Invalid API token or API access deactivated"
                        )

                    if response.status != 200:
                        raise TimebutlerApiError(
                            f"API request failed: {response.status} - {text}"
                        )

                    return text

        except asyncio.TimeoutError as err:
            raise TimebutlerConnectionError(
                f"Timeout connecting to Timebutler API: {err}"
            ) from err
        except aiohttp.ClientError as err:
            raise TimebutlerConnectionError(
                f"Error connecting to Timebutler API: {err}"
            ) from err

    def _parse_csv(self, text: str) -> list[dict[str, str]]:
        """Parse semicolon-delimited CSV response."""
        reader = csv.DictReader(io.StringIO(text), delimiter=";")
        return list(reader)

    def _parse_date(self, date_str: str) -> date | None:
        """Parse date in dd/mm/yyyy format."""
        if not date_str or date_str.strip() == "":
            return None
        try:
            return datetime.strptime(date_str.strip(), "%d/%m/%Y").date()
        except ValueError:
            _LOGGER.warning("Could not parse date: %s", date_str)
            return None

    def _parse_bool(self, value: str) -> bool:
        """Parse boolean string."""
        return value.lower() == "true"

    async def async_get_users(self) -> list[User]:
        """Fetch all users."""
        text = await self._request("users")
        rows = self._parse_csv(text)

        users = []
        for row in rows:
            try:
                user = User(
                    id=row.get("User ID", ""),
                    last_name=row.get("Last name", ""),
                    first_name=row.get("First name", ""),
                    email=row.get("E-mail address", ""),
                    department=row.get("Department") or None,
                    branch_office=row.get("Branch office") or None,
                    user_type=row.get("User type", ""),
                    is_locked=self._parse_bool(row.get("User account locked", "false")),
                )
                if user.id and not user.is_locked:
                    users.append(user)
            except (KeyError, ValueError) as err:
                _LOGGER.warning("Could not parse user row: %s - %s", row, err)

        return users

    async def async_get_absences(self, year: int | None = None) -> list[Absence]:
        """Fetch absences for a given year (defaults to current year)."""
        params = {}
        if year:
            params["year"] = str(year)

        text = await self._request("absences", params)
        rows = self._parse_csv(text)

        absences = []
        for row in rows:
            try:
                start_date = self._parse_date(row.get("From", ""))
                end_date = self._parse_date(row.get("To", ""))

                if not start_date or not end_date:
                    continue

                absence = Absence(
                    id=row.get("ID", ""),
                    user_id=row.get("User ID", ""),
                    absence_type=row.get("Type", ""),
                    start_date=start_date,
                    end_date=end_date,
                    state=row.get("State", ""),
                    half_day=self._parse_bool(row.get("Half a day", "false")),
                    morning=self._parse_bool(row.get("Morning", "false")),
                )
                absences.append(absence)
            except (KeyError, ValueError) as err:
                _LOGGER.warning("Could not parse absence row: %s - %s", row, err)

        return absences

    async def async_get_timeclock_status(self, user_id: str) -> TimeclockStatus:
        """Get timeclock status for a user."""
        text = await self._request(
            "timeclock",
            params={"command": "status", "userid": user_id},
        )

        # Response format: Result;Status;StartTimestamp;PauseTimestamp
        parts = text.strip().split(";")

        if len(parts) < 4:
            _LOGGER.warning("Unexpected timeclock response: %s", text)
            return TimeclockStatus(
                user_id=user_id,
                state=TIMECLOCK_IDLE,
                start_time=None,
                pause_time=None,
            )

        result, state, start_ts, pause_ts = parts[:4]

        if result not in ("OK", "WARN_TIMECLOCK_ALREADY_RUNNING"):
            _LOGGER.warning("Timeclock status error for user %s: %s", user_id, result)

        start_time = None
        pause_time = None

        try:
            if start_ts and start_ts != "0":
                start_time = datetime.fromtimestamp(int(start_ts) / 1000)
        except (ValueError, OSError) as err:
            _LOGGER.warning("Could not parse start timestamp: %s - %s", start_ts, err)

        try:
            if pause_ts and pause_ts != "0":
                pause_time = datetime.fromtimestamp(int(pause_ts) / 1000)
        except (ValueError, OSError) as err:
            _LOGGER.warning("Could not parse pause timestamp: %s - %s", pause_ts, err)

        return TimeclockStatus(
            user_id=user_id,
            state=state,
            start_time=start_time,
            pause_time=pause_time,
        )

    async def async_validate_token(self) -> bool:
        """Validate the API token by fetching users."""
        try:
            await self.async_get_users()
            return True
        except TimebutlerAuthError:
            return False
