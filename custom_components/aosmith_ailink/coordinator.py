"""Data coordinator for A. O. Smith AILink."""

from __future__ import annotations

from datetime import timedelta
import logging
from time import monotonic
from typing import Any

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import AOSmithApiError, AOSmithClient, AOSmithDevice

_LOGGER = logging.getLogger(__name__)


class AOSmithCoordinator(DataUpdateCoordinator[dict[str, AOSmithDevice]]):
    """Fetch AILink device data."""

    def __init__(self, hass, client: AOSmithClient, scan_interval: int) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name="A. O. Smith AILink",
            update_interval=timedelta(seconds=scan_interval),
        )
        self.client = client
        self.last_raw_realtime: dict[str, dict[str, Any]] = {}
        self._optimistic_updates: dict[str, dict[str, tuple[Any, float]]] = {}

    def async_update_device_cache(
        self,
        device_id: str,
        updates: dict[str, Any],
        duration: float = 30.0,
    ) -> None:
        """Optimistically update the cached raw payload for a device and notify entities."""
        device = self.data.get(device_id) if self.data else None
        if not device:
            return

        expires = monotonic() + duration
        device_optimistic = self._optimistic_updates.setdefault(device_id, {})
        for k, v in updates.items():
            device_optimistic[k] = (v, expires)

        merged = dict(device.raw)
        merged.update(updates)
        self.data[device_id] = AOSmithDevice(
            device_id=device.device_id,
            name=device.name,
            model=device.model,
            online=device.online,
            raw=merged,
        )
        self.async_update_listeners()

    def _apply_optimistic_overrides(self, device_id: str, raw: dict[str, Any]) -> dict[str, Any]:
        """Apply active optimistic overrides to prevent state bounce during cloud poll lag."""
        device_optimistic = self._optimistic_updates.get(device_id)
        if not device_optimistic:
            return raw

        now = monotonic()
        merged = dict(raw)
        expired_keys = []

        for key, (opt_val, expires) in device_optimistic.items():
            if now < expires:
                # If cloud already has the updated value, clear the optimistic entry
                if str(raw.get(key, "")) == str(opt_val):
                    expired_keys.append(key)
                else:
                    merged[key] = opt_val
            else:
                expired_keys.append(key)

        for key in expired_keys:
            device_optimistic.pop(key, None)

        return merged

    async def _async_update_data(self) -> dict[str, AOSmithDevice]:
        try:
            devices = await self.client.async_get_devices()
        except AOSmithApiError as err:
            raise UpdateFailed(str(err)) from err

        result = {}
        for device in devices:
            merged = dict(device.raw)
            try:
                realtime = await self.client.async_get_realtime(device.device_id)
                self.last_raw_realtime[device.device_id] = realtime
                if isinstance(realtime.get("data"), dict):
                    merged.update(realtime["data"])
            except AOSmithApiError as err:
                _LOGGER.debug("Realtime endpoint unavailable for %s: %s", device.device_id, err)

            merged = self._apply_optimistic_overrides(device.device_id, merged)
            result[device.device_id] = AOSmithDevice(
                device_id=device.device_id,
                name=device.name,
                model=device.model,
                online=device.online,
                raw=merged,
            )
        return result
