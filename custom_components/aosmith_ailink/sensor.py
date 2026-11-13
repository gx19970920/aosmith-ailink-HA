"""Sensors for A. O. Smith AILink."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    UnitOfPressure,
    UnitOfTemperature,
    UnitOfTime,
)
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


def _as_float(value: Any) -> float | None:
    """Coerce a number."""

    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _heating_pressure_bar(raw: dict[str, Any]) -> float | None:
    """Return heating water pressure in bar."""

    pressure_value = _as_float(_lookup(raw, ("pressureValue",)))
    if pressure_value is not None:
        return round(pressure_value / 10, 1)
    number = _as_float(
        _lookup(
            raw,
            (
                "heatingWaterPressure",
                "heatWaterPressure",
                "heatingPressure",
                "heatPressure",
                "systemPressure",
                "sysPressure",
                "waterPressure",
                "pressure",
            ),
        )
    )
    if number is None:
        return None
    return number


def _co_status(raw: dict[str, Any]) -> str | int | float | None:
    """Return the CO status shown by the app."""

    status = _lookup(raw, ("COStatus", "coStatus", "COState", "coState", "isCOOverStandard"))
    if status is not None:
        text = str(status).strip()
        if text in {"0", "false", "False"}:
            return "正常"
        if text in {"1", "true", "True"}:
            return "异常"
        return text
    return _lookup(raw, ("COValue", "coValue", "coConcentration", "COConcentration", "co", "CO"))


@dataclass(frozen=True, kw_only=True)
class AOSmithSensorDescription(SensorEntityDescription):
    """Sensor description."""

    value_fn: Callable[[dict[str, Any]], Any]


SENSORS = (
    AOSmithSensorDescription(
        key="heating_water_pressure",
        name="采暖水压",
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPressure.BAR,
        value_fn=_heating_pressure_bar,
    ),
    AOSmithSensorDescription(
        key="co_concentration",
        name="CO浓度",
        icon="mdi:molecule-co",
        value_fn=_co_status,
    ),
    AOSmithSensorDescription(
        key="heating_outlet_temperature",
        name="采暖出水温度",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda raw: _lookup(
            raw,
            (
                "heatingOutTEMP",
                "heatOutTEMP",
                "chOutTEMP",
                "CHOutTEMP",
                "heatingOutletTEMP",
                "heatingOutletTemp",
                "heatingSupplyTEMP",
                "heatingSupplyTemp",
                "heatingWaterOutTEMP",
                "heatingWaterOutTemp",
                "heatWaterOutTEMP",
                "heatWaterOutTemp",
                "warmOutTEMP",
                "warmOutTemp",
                "outWaterTemp",
                "supplyWaterTemp",
            ),
        ),
    ),
    AOSmithSensorDescription(
        key="heating_return_temperature",
        name="采暖回水温度",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda raw: _lookup(
            raw,
            (
                "heatingBackTEMP",
                "heatBackTEMP",
                "heatingReturnTEMP",
                "heatingReturnTemp",
                "heatReturnTEMP",
                "heatReturnTemp",
                "chReturnTEMP",
                "CHReturnTEMP",
                "heatingWaterInTEMP",
                "heatingWaterInTemp",
                "heatWaterInTEMP",
                "heatWaterInTemp",
                "warmInTEMP",
                "warmInTemp",
                "returnWaterTemp",
                "backWaterTemp",
            ),
        ),
    ),
    AOSmithSensorDescription(
        key="domestic_hot_water_current_temperature",
        name="当前热水温度",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda raw: _lookup(raw, ("waterOutTEMP", "currentTemp", "currTemp", "roomTemp", "temperature")),
    ),
    AOSmithSensorDescription(
        key="domestic_hot_water_target_temperature",
        name="设定热水温度",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda raw: _lookup(raw, ("waterTEMP", "targetTemp", "setTemp", "temperatureSet", "heatTemp")),
    ),
    AOSmithSensorDescription(
        key="domestic_hot_water_flow_rate",
        name="生活热水流量",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="L/min",
        icon="mdi:water-pump",
        value_fn=lambda raw: _lookup(
            raw,
            (
                "waterFlow",
                "waterFlowRate",
                "dhwFlow",
                "dhwFlowRate",
                "domesticHotWaterFlow",
                "domesticHotWaterFlowRate",
                "hotWaterFlow",
                "hotWaterFlowRate",
                "waterOutFlow",
                "flow",
            ),
        ),
    ),
    AOSmithSensorDescription(
        key="cumulative_burning_time",
        name="累计燃烧时间",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfTime.DAYS,
        icon="mdi:fire",
        value_fn=lambda raw: _lookup(
            raw,
            (
                "burningTime",
                "burnTime",
                "totalBurningTime",
                "totalBurnTime",
                "accBurningTime",
                "accBurnTime",
                "cumulativeBurningTime",
                "cumulativeBurnTime",
                "deviceFireTime",
                "burningDays",
                "burnDays",
                "useDays",
            ),
        ),
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
