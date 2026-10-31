"""Entity helpers for A. O. Smith AILink."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AOSmithCoordinator


class AOSmithEntity(CoordinatorEntity[AOSmithCoordinator]):
    """Base entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: AOSmithCoordinator, device_id: str) -> None:
        super().__init__(coordinator)
        self.device_id = device_id
        self._attr_unique_id = f"{DOMAIN}_{device_id}_{self.entity_description.key}"
        self._attr_suggested_object_id = f"aosmith_{device_id.lower()}_{self.entity_description.key}"

    @property
    def device(self):
        """Return the current device payload."""

        return self.coordinator.data.get(self.device_id)

    @property
    def device_info(self) -> DeviceInfo:
        """Return Home Assistant device info."""

        device = self.device
        return DeviceInfo(
            identifiers={(DOMAIN, self.device_id)},
            manufacturer="A. O. Smith",
            name=device.name if device else self.device_id,
            model=device.model if device else None,
        )
