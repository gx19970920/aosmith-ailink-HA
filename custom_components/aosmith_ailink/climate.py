"""Climate entities for A. O. Smith wall-hung boilers."""

from __future__ import annotations

from dataclasses import dataclass
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


HEATING_STATE_KEYS = (
    "centralHeating",
    "SHC_On",
    "heatingMode",
    "centralHeatingMode",
    "heatingOnOff",
    "heatOnOff",
    "heatingEnabled",
    "heatEnabled",
    "heatingSwitch",
    "heatSwitch",
    "heatingStatus",
    "heatStatus",
    "heating",
    "isHeatingOn",
    "CHOnOff",
    "chOnOff",
    "warmStatus",
)


def _lookup(raw: dict[str, Any], keys: tuple[str, ...]) -> Any:
    lowered = {str(key).lower(): value for key, value in raw.items()}
    for key in keys:
        if key in raw:
            return raw[key]
        if key.lower() in lowered:
            return lowered[key.lower()]
    return None


def _coerce_optional_bool(value: Any) -> bool | None:
    """Coerce common cloud on/off values."""

    if value is None:
        return None
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "on", "open", "enabled", "enable", "yes", "y"}:
        return True
    if text in {"0", "false", "off", "closed", "disabled", "disable", "no", "n"}:
        return False
    return None


@dataclass(frozen=True, kw_only=True)
class AOSmithClimateDescription(ClimateEntityDescription):
    """Description for a boiler climate function."""

    command_type: str
    current_temperature_keys: tuple[str, ...]
    target_temperature_keys: tuple[str, ...]
    min_temperature_keys: tuple[str, ...]
    max_temperature_keys: tuple[str, ...]
    fallback_min_temp: float
    fallback_max_temp: float
    supports_hvac_mode: bool = False


CLIMATES = (
    AOSmithClimateDescription(
        key="hot_water",
        name="热水",
        command_type="0",
        current_temperature_keys=("waterOutTEMP", "currentTemp", "currTemp", "roomTemp", "temperature"),
        target_temperature_keys=("waterTEMP", "targetTemp", "setTemp", "temperatureSet", "heatTemp"),
        min_temperature_keys=("waterTempSetMin",),
        max_temperature_keys=("waterTempSetMax",),
        fallback_min_temp=35,
        fallback_max_temp=60,
    ),
    AOSmithClimateDescription(
        key="space_heating",
        name="采暖",
        command_type="1",
        current_temperature_keys=(
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
            "heatingCurrentTemp",
            "heatCurrentTemp",
            "roomTemp",
        ),
        target_temperature_keys=(
            "heatingTEMP",
            "heatingTemp",
            "heatTEMP",
            "heatTemp",
            "heatingWaterTEMP",
            "heatingWaterTemp",
            "heatWaterTEMP",
            "heatWaterTemp",
            "warmTemp",
            "shcSetTemp",
            "chTEMP",
            "CHTEMP",
            "chTemp",
            "CHTemp",
            "heatingSetTEMP",
            "heatSetTEMP",
            "chSetTEMP",
            "CHSetTEMP",
            "heatingSetTemp",
            "heatSetTemp",
            "heatingTempSet",
            "heatTempSet",
            "heatingTargetTemp",
            "heatTargetTemp",
        ),
        min_temperature_keys=(
            "warmTempSetMin",
            "heatingTempSetMin",
            "heatTempSetMin",
            "chTempSetMin",
            "CHTempSetMin",
            "SHC_OutputMinTemp",
        ),
        max_temperature_keys=(
            "warmTempSetMax",
            "warmAllowMaxSetTemp",
            "heatingTempSetMax",
            "heatTempSetMax",
            "chTempSetMax",
            "CHTempSetMax",
        ),
        fallback_min_temp=30,
        fallback_max_temp=80,
        supports_hvac_mode=True,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up climate entities."""

    coordinator: AOSmithCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        AOSmithBoilerClimate(coordinator, device_id, description)
        for device_id in coordinator.data
        for description in CLIMATES
    )


class AOSmithBoilerClimate(AOSmithEntity, ClimateEntity):
    """Wall-hung boiler climate entity."""

    entity_description: AOSmithClimateDescription
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = 1

    def __init__(
        self,
        coordinator: AOSmithCoordinator,
        device_id: str,
        description: AOSmithClimateDescription,
    ) -> None:
        self.entity_description = description
        self._optimistic_hvac_mode: HVACMode | None = None
        self._optimistic_target_temperature: float | None = None
        super().__init__(coordinator, device_id)
        if description.key == "hot_water":
            self._attr_has_entity_name = False

    @property
    def hvac_modes(self) -> list[HVACMode]:
        """Return supported HVAC modes."""

        if self.entity_description.supports_hvac_mode:
            return [HVACMode.OFF, HVACMode.HEAT]
        return [HVACMode.HEAT]

    @property
    def min_temp(self) -> float:
        """Return minimum target temperature."""

        if not self.device:
            return self.entity_description.fallback_min_temp
        return (
            _as_float(_lookup(self.device.raw, self.entity_description.min_temperature_keys))
            or self.entity_description.fallback_min_temp
        )

    @property
    def max_temp(self) -> float:
        """Return maximum target temperature."""

        if not self.device:
            return self.entity_description.fallback_max_temp
        return (
            _as_float(_lookup(self.device.raw, self.entity_description.max_temperature_keys))
            or self.entity_description.fallback_max_temp
        )

    @property
    def current_temperature(self) -> float | None:
        """Return current temperature."""

        if not self.device:
            return None
        value = _lookup(self.device.raw, self.entity_description.current_temperature_keys)
        return _as_float(value)

    @property
    def target_temperature(self) -> float | None:
        """Return target temperature."""

        if not self.device:
            return None
        value = _lookup(self.device.raw, self.entity_description.target_temperature_keys)
        if value is not None:
            return _as_float(value)
        if self._optimistic_target_temperature is not None:
            return self._optimistic_target_temperature
        if self.entity_description.supports_hvac_mode:
            return self.current_temperature or self.entity_description.fallback_min_temp
        return None

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Return HVAC mode."""

        if not self.entity_description.supports_hvac_mode:
            return HVACMode.HEAT
        if not self.device:
            return self._optimistic_hvac_mode or HVACMode.HEAT
        enabled = _coerce_optional_bool(_lookup(self.device.raw, HEATING_STATE_KEYS))
        if enabled is None:
            return self._optimistic_hvac_mode or HVACMode.HEAT
        return HVACMode.HEAT if enabled else HVACMode.OFF

    async def async_turn_on(self) -> None:
        """Turn heating mode on."""

        if self.entity_description.supports_hvac_mode:
            await self.async_set_hvac_mode(HVACMode.HEAT)

    async def async_turn_off(self) -> None:
        """Turn heating mode off."""

        if self.entity_description.supports_hvac_mode:
            await self.async_set_hvac_mode(HVACMode.OFF)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set heating mode on or off."""

        if not self.entity_description.supports_hvac_mode:
            return
        if hvac_mode not in (HVACMode.OFF, HVACMode.HEAT):
            return
        await self.coordinator.client.async_set_heating_enabled(
            self.device_id,
            hvac_mode == HVACMode.HEAT,
            product_type=_product_type(self.device.raw) if self.device else "24",
            device_type=_device_type(self.device.raw) if self.device else None,
        )
        self._optimistic_hvac_mode = hvac_mode
        val_str = "1" if hvac_mode == HVACMode.HEAT else "0"
        self.coordinator.async_update_device_cache(
            self.device_id,
            {key: val_str for key in HEATING_STATE_KEYS},
        )
        await self.coordinator.async_request_refresh()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set target temperature through the app-style invoke endpoint."""

        if ATTR_TEMPERATURE not in kwargs:
            return
        temperature = float(kwargs[ATTR_TEMPERATURE])
        product_type = _product_type(self.device.raw) if self.device else "24"
        device_type = _device_type(self.device.raw) if self.device else None
        if self.entity_description.command_type == "1":
            await self.coordinator.client.async_set_heating_temperature(
                self.device_id,
                temperature,
                product_type=product_type,
                device_type=device_type,
            )
        else:
            await self.coordinator.client.async_set_water_temperature(
                self.device_id,
                temperature,
                product_type=product_type,
                device_type=device_type,
            )
        self._optimistic_target_temperature = temperature
        updates = {key: temperature for key in self.entity_description.target_temperature_keys}
        self.coordinator.async_update_device_cache(self.device_id, updates)
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
