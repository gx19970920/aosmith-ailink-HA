"""Switches for A. O. Smith AILink."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import AOSmithCoordinator
from .entity import AOSmithEntity


def _lookup(raw: dict[str, Any], keys: tuple[str, ...]) -> Any:
    lowered = {str(key).lower(): value for key, value in raw.items()}
    for key in keys:
        if key in raw:
            return raw[key]
        if key.lower() in lowered:
            return lowered[key.lower()]
    return None


@dataclass(frozen=True, kw_only=True)
class AOSmithQuickWashSwitchDescription(SwitchEntityDescription):
    """Description for a quick-wash switch."""

    command_value: str


QUICK_WASH_SWITCHES = (
    AOSmithQuickWashSwitchDescription(
        key="one_key_quick_wash",
        name="一键速热洗",
        command_value="1",
    ),
    AOSmithQuickWashSwitchDescription(
        key="quick_wash_24h",
        name="24小时速热洗",
        command_value="2",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switches."""

    coordinator: AOSmithCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        AOSmithQuickWashSwitch(coordinator, device_id, description)
        for device_id in coordinator.data
        for description in QUICK_WASH_SWITCHES
    )


class AOSmithQuickWashSwitch(AOSmithEntity, SwitchEntity):
    """Mutually-exclusive quick-wash mode switch."""

    entity_description: AOSmithQuickWashSwitchDescription

    def __init__(
        self,
        coordinator: AOSmithCoordinator,
        device_id: str,
        description: AOSmithQuickWashSwitchDescription,
    ) -> None:
        self.entity_description = description
        super().__init__(coordinator, device_id)

    @property
    def is_on(self) -> bool | None:
        """Return whether this quick-wash mode is active."""

        if not self.device:
            return None
        return str(_lookup(self.device.raw, ("preWork", "prework")) or "0") == self.entity_description.command_value

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on this quick-wash mode.

        The device represents quick wash as a single enum-like SetCruiseOnOff
        value, so setting one mode naturally disables the other mode.
        """

        if self.is_on:
            return
        await self.coordinator.client.async_start_quick_wash(
            self.device_id,
            "one_key" if self.entity_description.command_value == "1" else "24h",
            product_type=_product_type(self.device.raw) if self.device else "24",
            device_type=_device_type(self.device.raw) if self.device else None,
        )
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off quick wash if this mode is active."""

        if not self.is_on:
            return
        await self.coordinator.client.async_stop_quick_wash(
            self.device_id,
            product_type=_product_type(self.device.raw) if self.device else "24",
            device_type=_device_type(self.device.raw) if self.device else None,
        )
        await self.coordinator.async_request_refresh()


def _product_type(raw: dict[str, Any]) -> str:
    """Return the product type required by invokeMethod.profile."""

    return str(
        _lookup(raw, ("productMajorClassCode", "deviceCategory", "profile_productType", "productType"))
        or "24"
    )


def _device_type(raw: dict[str, Any]) -> str | None:
    """Return the device type required by invokeMethod.profile."""

    value = _lookup(raw, ("profile_deviceType", "deviceModel", "productModel", "deviceType"))
    return str(value) if value else None
