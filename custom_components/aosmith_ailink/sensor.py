"""Sensors for A. O. Smith AILink."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
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
class AOSmithSensorDescription(SensorEntityDescription):
    """Sensor description."""

    value_fn: Callable[[dict[str, Any]], Any]


SENSORS = (
    AOSmithSensorDescription(
        key="current_temperature",
        name="当前热水温度",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda raw: _lookup(raw, ("waterOutTEMP", "currentTemp", "currTemp", "roomTemp", "temperature")),
    ),
    AOSmithSensorDescription(
        key="target_temperature",
        name="设定热水温度",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda raw: _lookup(raw, ("waterTEMP", "targetTemp", "setTemp", "temperatureSet", "heatTemp")),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors."""

    coordinator: AOSmithCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        AOSmithSensor(coordinator, device_id, description)
        for device_id in coordinator.data
        for description in SENSORS
    )


class AOSmithSensor(AOSmithEntity, SensorEntity):
    """A generic sensor backed by the raw device payload."""

    entity_description: AOSmithSensorDescription

    def __init__(
        self,
        coordinator: AOSmithCoordinator,
        device_id: str,
        description: AOSmithSensorDescription,
    ) -> None:
        self.entity_description = description
        super().__init__(coordinator, device_id)

    @property
    def native_value(self):
        """Return the sensor state."""

        if not self.device:
            return None
        return self.entity_description.value_fn(self.device.raw)
