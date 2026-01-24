"""Sensor platform for Timebutler integration."""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, STATUS_OFF, STATUS_PAUSED, STATUS_WORKING
from .coordinator import TimebutlerData, TimebutlerDataUpdateCoordinator, UserStatus

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Timebutler sensors from a config entry."""
    coordinator: TimebutlerDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[SensorEntity] = []

    # Create individual user sensors
    for user_id in coordinator.data.users:
        entities.append(TimebutlerUserSensor(coordinator, entry, user_id))

    # Create overall group sensors
    entities.append(TimebutlerGroupSensor(coordinator, entry, STATUS_WORKING, None))
    entities.append(TimebutlerGroupSensor(coordinator, entry, STATUS_PAUSED, None))

    # Create dynamic sensors for each absence type found
    absence_types = {
        status.current_absence.absence_type.lower().replace(" ", "_")
        for status in coordinator.data.user_statuses.values()
        if status.current_absence
    }
    for absence_type in absence_types:
        entities.append(TimebutlerGroupSensor(coordinator, entry, absence_type, None))

    # Create per-department group sensors
    for department in coordinator.data.departments:
        entities.append(
            TimebutlerGroupSensor(coordinator, entry, STATUS_WORKING, department)
        )

    async_add_entities(entities)


def _slugify(text: str) -> str:
    """Create a slug from text."""
    return text.lower().replace(" ", "_").replace("-", "_")


class TimebutlerUserSensor(CoordinatorEntity[TimebutlerDataUpdateCoordinator], SensorEntity):
    """Sensor representing a Timebutler user's status."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: TimebutlerDataUpdateCoordinator,
        entry: ConfigEntry,
        user_id: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._user_id = user_id
        self._attr_unique_id = f"{entry.entry_id}_{user_id}"

        user = coordinator.data.users[user_id]
        self._attr_name = user.name
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Timebutler",
            manufacturer="Timebutler",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def user_status(self) -> UserStatus | None:
        """Get current user status."""
        return self.coordinator.data.user_statuses.get(self._user_id)

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        if status := self.user_status:
            return status.status
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        if not (status := self.user_status):
            return {}

        attrs: dict[str, Any] = {
            "user_id": self._user_id,
            "email": status.user.email,
            "department": status.user.department,
            "branch_office": status.user.branch_office,
            "user_type": status.user.user_type,
        }

        if status.timeclock and status.timeclock.start_time:
            attrs["clock_in_time"] = status.timeclock.start_time.isoformat()

        if status.current_absence:
            attrs["absence_type"] = status.current_absence.absence_type
            attrs["absence_start"] = status.current_absence.start_date.isoformat()
            attrs["absence_end"] = status.current_absence.end_date.isoformat()

        return attrs

    @property
    def icon(self) -> str:
        """Return the icon for the sensor."""
        if status := self.user_status:
            if status.status == STATUS_WORKING:
                return "mdi:account-clock"
            if status.status == STATUS_PAUSED:
                return "mdi:account-clock-outline"
            if status.is_absent:
                return "mdi:account-off"
        return "mdi:account"


class TimebutlerGroupSensor(CoordinatorEntity[TimebutlerDataUpdateCoordinator], SensorEntity):
    """Sensor representing a count of users in a particular status."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: TimebutlerDataUpdateCoordinator,
        entry: ConfigEntry,
        status_filter: str,
        department: str | None,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._status_filter = status_filter
        self._department = department

        # Build unique ID and name
        if department:
            dept_slug = _slugify(department)
            self._attr_unique_id = f"{entry.entry_id}_group_{dept_slug}_{status_filter}"
            self._attr_name = f"{department} - {self._status_display}"
        else:
            self._attr_unique_id = f"{entry.entry_id}_group_{status_filter}"
            self._attr_name = f"People {self._status_display}"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Timebutler",
            manufacturer="Timebutler",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def _status_display(self) -> str:
        """Get display name for the status."""
        if self._status_filter == STATUS_WORKING:
            return "Working"
        if self._status_filter == STATUS_PAUSED:
            return "On Break"
        # Absence types
        return f"On {self._status_filter.replace('_', ' ').title()}"

    def _get_matching_users(self) -> list[UserStatus]:
        """Get users matching the filter criteria."""
        matching = []
        for user_status in self.coordinator.data.user_statuses.values():
            # Filter by department if specified
            if self._department and user_status.user.department != self._department:
                continue

            # Filter by status
            if user_status.status == self._status_filter:
                matching.append(user_status)

        return matching

    @property
    def native_value(self) -> int:
        """Return the count of users."""
        return len(self._get_matching_users())

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        matching = self._get_matching_users()
        return {
            "names": [status.user.name for status in matching],
            "user_ids": [status.user.id for status in matching],
            "count": len(matching),
        }

    @property
    def icon(self) -> str:
        """Return the icon for the sensor."""
        if self._status_filter == STATUS_WORKING:
            return "mdi:account-group"
        if self._status_filter == STATUS_PAUSED:
            return "mdi:account-group-outline"
        return "mdi:account-multiple-remove"
