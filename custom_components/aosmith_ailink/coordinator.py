"""Data coordinator for A. O. Smith AILink."""

from __future__ import annotations

from datetime import timedelta
import logging
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

    async def _async_update_data(self) -> dict[str, AOSmithDevice]:
        try:
            devices = await self.client.async_get_devices()
        except AOSmithApiError as err:
            raise UpdateFailed(str(err)) from err

        result = {device.device_id: device for device in devices}
        for device in devices:
            try:
                realtime = await self.client.async_get_realtime(device.device_id)
            except AOSmithApiError:
                _LOGGER.debug("Realtime endpoint unavailable")
                continue
            self.last_raw_realtime[device.device_id] = realtime
            if isinstance(realtime.get("data"), dict):
                merged = dict(device.raw)
                merged.update(realtime["data"])
                result[device.device_id] = AOSmithDevice(
                    device_id=device.device_id,
                    name=device.name,
                    model=device.model,
                    online=device.online,
                    raw=merged,
                )
        return result
