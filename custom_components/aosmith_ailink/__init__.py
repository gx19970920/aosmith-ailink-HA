"""A. O. Smith China AILink custom integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_SCAN_INTERVAL, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import voluptuous as vol

from .api import AOSmithClient
from .const import (
    CONF_ACCESS_TOKEN,
    CONF_BASE_URL,
    CONF_DEVICE_ID,
    CONF_FAMILY_ID,
    CONF_MOBILE,
    CONF_USER_ID,
    CONF_VERIFY_SSL,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TIMEOUT,
    DOMAIN,
    PLATFORMS,
    SERVICE_INVOKE_METHOD,
    SERVICE_SET_HEATING,
    SERVICE_START_24H_QUICK_WASH,
    SERVICE_START_ONE_KEY_QUICK_WASH,
)
from .coordinator import AOSmithCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up integration services."""

    hass.data.setdefault(DOMAIN, {})

    async def async_invoke_method(call: ServiceCall) -> None:
        coordinator = _coordinator_from_call(hass, call)
        device_id = _device_id_from_call(call, coordinator)
        method = call.data["method"]
        params = call.data.get("params") or {}
        response = await coordinator.client.async_invoke_method(device_id, method, params)
        _LOGGER.info("A. O. Smith invoke_method response: %s", response)
        await coordinator.async_request_refresh()

    async def async_set_heating(call: ServiceCall) -> None:
        coordinator = _coordinator_from_call(hass, call)
        device_id = _device_id_from_call(call, coordinator)
        product_type, device_type = _device_profile(coordinator, device_id)
        enabled = call.data["enabled"]
        response = await coordinator.client.async_set_heating_enabled(
            device_id,
            enabled,
            product_type=product_type,
            device_type=device_type,
        )
        _LOGGER.info("A. O. Smith set_heating response: %s", response)
        val_str = "1" if enabled else "0"
        coordinator.async_update_device_cache(
            device_id,
            {
                "centralHeating": val_str,
                "SHC_On": val_str,
                "heatingMode": val_str,
                "heatingOnOff": val_str,
                "heatOnOff": val_str,
                "heatingEnabled": val_str,
                "heatingSwitch": val_str,
            },
        )
        await coordinator.async_request_refresh()

    async def async_start_one_key_quick_wash(call: ServiceCall) -> None:
        coordinator = _coordinator_from_call(hass, call)
        device_id = _device_id_from_call(call, coordinator)
        product_type, device_type = _device_profile(coordinator, device_id)
        response = await coordinator.client.async_start_quick_wash(
            device_id,
            "one_key",
            product_type=product_type,
            device_type=device_type,
        )
        _LOGGER.info("A. O. Smith one-key quick wash response: %s", response)
        coordinator.async_update_device_cache(device_id, {"preWork": "1", "prework": "1"})
        await coordinator.async_request_refresh()

    async def async_start_24h_quick_wash(call: ServiceCall) -> None:
        coordinator = _coordinator_from_call(hass, call)
        device_id = _device_id_from_call(call, coordinator)
        product_type, device_type = _device_profile(coordinator, device_id)
        response = await coordinator.client.async_start_quick_wash(
            device_id,
            "24h",
            product_type=product_type,
            device_type=device_type,
        )
        _LOGGER.info("A. O. Smith 24-hour quick wash response: %s", response)
        coordinator.async_update_device_cache(device_id, {"preWork": "2", "prework": "2"})
        await coordinator.async_request_refresh()

    hass.services.async_register(
        DOMAIN,
        SERVICE_INVOKE_METHOD,
        async_invoke_method,
        schema=vol.Schema(
            {
                vol.Optional(CONF_DEVICE_ID): str,
                vol.Optional("entry_id"): str,
                vol.Required("method"): str,
                vol.Optional("params", default={}): dict,
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_HEATING,
        async_set_heating,
        schema=vol.Schema(
            {
                vol.Optional(CONF_DEVICE_ID): str,
                vol.Optional("entry_id"): str,
                vol.Required("enabled"): bool,
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_START_ONE_KEY_QUICK_WASH,
        async_start_one_key_quick_wash,
        schema=vol.Schema({vol.Optional(CONF_DEVICE_ID): str, vol.Optional("entry_id"): str}),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_START_24H_QUICK_WASH,
        async_start_24h_quick_wash,
        schema=vol.Schema({vol.Optional(CONF_DEVICE_ID): str, vol.Optional("entry_id"): str}),
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up from a config entry."""

    data = entry.data
    options = entry.options
    access_token = options.get(CONF_ACCESS_TOKEN, data.get(CONF_ACCESS_TOKEN))
    verify_ssl = options.get(CONF_VERIFY_SSL, data.get(CONF_VERIFY_SSL, True))
    session = async_get_clientsession(hass, verify_ssl=verify_ssl)
    client = AOSmithClient(
        session,
        data[CONF_BASE_URL],
        username=data.get(CONF_USERNAME),
        password=data.get(CONF_PASSWORD),
        access_token=access_token,
        family_id=data.get(CONF_FAMILY_ID),
        mobile=data.get(CONF_MOBILE),
        user_id=data.get(CONF_USER_ID),
        device_id=data.get(CONF_DEVICE_ID),
        timeout=DEFAULT_TIMEOUT,
        verify_ssl=verify_ssl,
    )
    if not client.access_token and data.get(CONF_USERNAME) and data.get(CONF_PASSWORD):
        await client.async_login()

    coordinator = AOSmithCoordinator(
        hass,
        client,
        int(options.get(CONF_SCAN_INTERVAL, data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))),
    )
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, [Platform(platform) for platform in PLATFORMS])
    entry.async_on_unload(entry.add_update_listener(update_listener))

    return True


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    unloaded = await hass.config_entries.async_unload_platforms(
        entry, [Platform(platform) for platform in PLATFORMS]
    )
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unloaded


def _coordinator_from_call(hass: HomeAssistant, call: ServiceCall) -> AOSmithCoordinator:
    """Return the coordinator targeted by a service call."""

    coordinators: dict[str, AOSmithCoordinator] = hass.data.get(DOMAIN, {})
    if not coordinators:
        raise HomeAssistantError("No A. O. Smith AILink config entry is loaded")

    entry_id = call.data.get("entry_id")
    if entry_id:
        coordinator = coordinators.get(entry_id)
        if not coordinator:
            raise HomeAssistantError(f"A. O. Smith AILink entry_id not found: {entry_id}")
        return coordinator

    device_id = call.data.get(CONF_DEVICE_ID)
    if device_id:
        for coordinator in coordinators.values():
            if device_id in coordinator.data or coordinator.client.configured_device_id == device_id:
                return coordinator
        raise HomeAssistantError(f"A. O. Smith device_id not found: {device_id}")

    if len(coordinators) == 1:
        return next(iter(coordinators.values()))

    raise HomeAssistantError("Multiple A. O. Smith entries are loaded; pass entry_id or device_id")


def _device_id_from_call(call: ServiceCall, coordinator: AOSmithCoordinator) -> str:
    """Return service device id from call data or config."""

    device_id = call.data.get(CONF_DEVICE_ID) or coordinator.client.configured_device_id
    if not device_id and len(coordinator.data) == 1:
        device_id = next(iter(coordinator.data))
    if not device_id:
        raise HomeAssistantError("device_id is required when it is not configured")
    return str(device_id)


def _device_profile(coordinator: AOSmithCoordinator, device_id: str) -> tuple[str, str | None]:
    """Return productType and deviceType for service payloads."""

    device = coordinator.data.get(device_id)
    raw = device.raw if device else {}
    product_type = (
        raw.get("productMajorClassCode")
        or raw.get("deviceCategory")
        or raw.get("profile_productType")
        or raw.get("productType")
        or "24"
    )
    device_type = raw.get("profile_deviceType") or raw.get("deviceModel") or raw.get("productModel") or raw.get("deviceType")
    return str(product_type), str(device_type) if device_type else None
