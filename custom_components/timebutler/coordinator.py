"""Data coordinator for Timebutler integration."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import date, timedelta
from typing import TYPE_CHECKING

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    Absence,
    TimebutlerApiClient,
    TimebutlerApiError,
    TimebutlerAuthError,
    TimeclockStatus,
    User,
)
from .const import (
    ABSENCE_STATE_APPROVED,
    ABSENCE_STATE_DONE,
    DOMAIN,
    STATUS_OFF,
    STATUS_PAUSED,
    STATUS_WORKING,
)

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry

_LOGGER = logging.getLogger(__name__)

# Maximum concurrent timeclock requests
MAX_CONCURRENT_TIMECLOCK = 5


@dataclass
class UserStatus:
    """Computed status for a user."""

    user: User
    status: str  # working, paused, off, or absence type (vacation, sick, etc.)
    timeclock: TimeclockStatus | None
    current_absence: Absence | None

    @property
    def is_absent(self) -> bool:
        """Return True if user is on an approved absence."""
        return self.current_absence is not None

    @property
    def status_display(self) -> str:
        """Return display-friendly status."""
        return self.status.replace("_", " ").title()


@dataclass
class TimebutlerData:
    """Data from Timebutler API."""

    users: dict[str, User]
    user_statuses: dict[str, UserStatus]
    absences: list[Absence]
    departments: set[str]


class TimebutlerDataUpdateCoordinator(DataUpdateCoordinator[TimebutlerData]):
    """Coordinator for fetching Timebutler data."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        client: TimebutlerApiClient,
        update_interval: timedelta,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=update_interval,
        )
        self.client = client

    async def _async_update_data(self) -> TimebutlerData:
        """Fetch data from Timebutler API."""
        try:
            # Fetch users and absences in parallel
            users_list, absences = await asyncio.gather(
                self.client.async_get_users(),
                self.client.async_get_absences(),
            )

            # Build user dictionary
            users = {user.id: user for user in users_list}

            # Fetch timeclock status for all users with concurrency limit
            timeclock_statuses = await self._fetch_timeclock_statuses(users_list)

            # Compute user statuses
            user_statuses = self._compute_user_statuses(
                users, absences, timeclock_statuses
            )

            # Extract unique departments
            departments = {
                user.department for user in users_list if user.department
            }

            return TimebutlerData(
                users=users,
                user_statuses=user_statuses,
                absences=absences,
                departments=departments,
            )

        except TimebutlerAuthError as err:
            raise UpdateFailed(f"Authentication failed: {err}") from err
        except TimebutlerApiError as err:
            raise UpdateFailed(f"Error communicating with Timebutler API: {err}") from err

    async def _fetch_timeclock_statuses(
        self, users: list[User]
    ) -> dict[str, TimeclockStatus]:
        """Fetch timeclock status for all users with concurrency limit."""
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_TIMECLOCK)
        statuses: dict[str, TimeclockStatus] = {}

        async def fetch_one(user: User) -> None:
            async with semaphore:
                try:
                    status = await self.client.async_get_timeclock_status(user.id)
                    statuses[user.id] = status
                except TimebutlerApiError as err:
                    _LOGGER.warning(
                        "Failed to fetch timeclock for user %s: %s", user.name, err
                    )
                    # Create idle status on error
                    statuses[user.id] = TimeclockStatus(
                        user_id=user.id,
                        state="IDLE",
                        start_time=None,
                        pause_time=None,
                    )

        await asyncio.gather(*[fetch_one(user) for user in users])
        return statuses

    def _compute_user_statuses(
        self,
        users: dict[str, User],
        absences: list[Absence],
        timeclock_statuses: dict[str, TimeclockStatus],
    ) -> dict[str, UserStatus]:
        """Compute status for each user."""
        today = date.today()
        user_statuses: dict[str, UserStatus] = {}

        # Index current absences by user
        current_absences: dict[str, Absence] = {}
        for absence in absences:
            # Only consider approved or done absences
            if absence.state not in (ABSENCE_STATE_APPROVED, ABSENCE_STATE_DONE):
                continue

            # Check if absence is active today
            if absence.start_date <= today <= absence.end_date:
                # Keep the most recent absence for each user
                existing = current_absences.get(absence.user_id)
                if existing is None or absence.start_date > existing.start_date:
                    current_absences[absence.user_id] = absence

        # Compute status for each user
        for user_id, user in users.items():
            timeclock = timeclock_statuses.get(user_id)
            absence = current_absences.get(user_id)

            # Priority: timeclock > absence > off
            if timeclock and timeclock.is_working:
                status = STATUS_WORKING
            elif timeclock and timeclock.is_paused:
                status = STATUS_PAUSED
            elif absence:
                # Use absence type as status (e.g., "vacation", "sick")
                status = absence.absence_type.lower().replace(" ", "_")
            else:
                status = STATUS_OFF

            user_statuses[user_id] = UserStatus(
                user=user,
                status=status,
                timeclock=timeclock,
                current_absence=absence,
            )

        return user_statuses
