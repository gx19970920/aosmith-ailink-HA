"""Climate entity for A. O. Smith wall-hung boilers."""

from __future__ import annotations

from typing import Any

from homeassistant.components.climate import ClimateEntity, ClimateEntityDescription
from homeassistant.components.climate.const import (
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
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


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up climate entities."""

    coordinator: AOSmithCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(AOSmithBoilerClimate(coordinator, device_id) for device_id in coordinator.data)


class AOSmithBoilerClimate(AOSmithEntity, ClimateEntity):
    """Best-effort wall-hung boiler climate entity."""

    entity_description = ClimateEntityDescription(key="climate", name=None)
    _attr_hvac_modes = [HVACMode.HEAT]
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = 1

    @property
    def min_temp(self) -> float:
        """Return minimum domestic hot-water temperature."""

        if not self.device:
            return 35
        return _as_float(_lookup(self.device.raw, ("waterTempSetMin",))) or 35

    @property
    def max_temp(self) -> float:
        """Return maximum domestic hot-water temperature."""

        if not self.device:
            return 60
        return _as_float(_lookup(self.device.raw, ("waterTempSetMax",))) or 60

    @property
    def current_temperature(self) -> float | None:
        """Return current temperature."""

        if not self.device:
            return None
        value = _lookup(self.device.raw, ("waterOutTEMP", "currentTemp", "currTemp", "roomTemp", "temperature"))
        return _as_float(value)

    @property
    def target_temperature(self) -> float | None:
        """Return target temperature."""

        if not self.device:
            return None
        value = _lookup(self.device.raw, ("waterTEMP", "targetTemp", "setTemp", "temperatureSet", "heatTemp"))
        return _as_float(value)

    @property
    def hvac_mode(self) -> HVACMode:
        """Return HVAC mode."""

        return HVACMode.HEAT

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set target temperature through the raw invoke endpoint."""

        if ATTR_TEMPERATURE not in kwargs:
            return
        await self.coordinator.client.async_set_water_temperature(
            self.device_id,
            kwargs[ATTR_TEMPERATURE],
            product_type=_product_type(self.device.raw) if self.device else "24",
            device_type=_device_type(self.device.raw) if self.device else None,
        )
        await self.coordinator.async_request_refresh()

def _as_float(value: Any) -> float | None:
    """Coerce a number."""

    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


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
