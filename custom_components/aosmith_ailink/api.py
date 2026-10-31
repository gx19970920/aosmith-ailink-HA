"""Cloud client for the A. O. Smith China AILink app."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from dataclasses import dataclass
import json as jsonlib
import logging
from typing import Any

from aiohttp import ClientError, ClientSession, ClientTimeout

from .const import (
    ENDPOINT_DEVICE_CURR_INFO,
    ENDPOINT_DEVICE_LIST,
    ENDPOINT_FAMILY_INDEX,
    ENDPOINT_FAMILY_LIST,
    ENDPOINT_HOMEPAGE_V2,
    ENDPOINT_INVOKE,
    ENDPOINT_LOGIN,
    ENDPOINT_REALTIME,
    ENDPOINT_USER_DEVICE_LIST,
)

_LOGGER = logging.getLogger(__name__)


class AOSmithApiError(Exception):
    """Raised when the AILink cloud returns an error."""


@dataclass(slots=True)
class AOSmithDevice:
    """Normalized device data with the original payload preserved."""

    device_id: str
    name: str
    model: str | None
    online: bool | None
    raw: dict[str, Any]


class AOSmithClient:
    """Small async client for the cloud APIs found in the Android APK."""

    def __init__(
        self,
        session: ClientSession,
        base_url: str,
        *,
        username: str | None = None,
        password: str | None = None,
        access_token: str | None = None,
        family_id: str | None = None,
        mobile: str | None = None,
        user_id: str | None = None,
        device_id: str | None = None,
        timeout: int = 20,
        verify_ssl: bool = True,
    ) -> None:
        self._session = session
        self._base_url = base_url.rstrip("/")
        self._username = username
        self._mobile = mobile or username
        self._password = password
        self._access_token = access_token
        self._family_id = family_id
        self._user_id = user_id
        self._device_id = device_id
        self._timeout = ClientTimeout(total=timeout)
        self._verify_ssl = verify_ssl

    @property
    def access_token(self) -> str | None:
        """Return the current access token."""

        return self._access_token

    @property
    def configured_device_id(self) -> str | None:
        """Return the configured device id."""

        return self._device_id

    async def async_login(self) -> dict[str, Any]:
        """Login with mobile/password if the account allows password login."""

        if not self._username or not self._password:
            raise AOSmithApiError("username/password not configured")

        # The APK exposes /user/login and strings named mobile/password/haxPassWord.
        # Some accounts may require SMS/Tencent captcha; in that case use token mode.
        payload = {"mobile": self._username, "password": self._password}
        data = await self._request("POST", ENDPOINT_LOGIN, json=payload, auth=False)
        token = _find_first(data, ("accessToken", "access_token", "token", "userToken"))
        if token:
            self._access_token = str(token)
        return data

    async def async_get_families(self) -> dict[str, Any]:
        """Fetch family information."""

        try:
            return await self._request("POST", ENDPOINT_FAMILY_LIST, json={})
        except AOSmithApiError:
            return await self._request("POST", ENDPOINT_FAMILY_INDEX, json={})

    async def async_get_devices(self) -> list[AOSmithDevice]:
        """Fetch and normalize devices."""

        payload: dict[str, Any] = {}
        if self._family_id:
            payload["familyId"] = self._family_id

        errors: list[Exception] = []
        for endpoint in (
            ENDPOINT_DEVICE_CURR_INFO,
            ENDPOINT_HOMEPAGE_V2,
            ENDPOINT_DEVICE_LIST,
            ENDPOINT_USER_DEVICE_LIST,
        ):
            try:
                request_payload = dict(payload)
                if endpoint == ENDPOINT_DEVICE_CURR_INFO and self._device_id:
                    request_payload["deviceId"] = self._device_id
                data = await self._request("POST", endpoint, json=request_payload)
            except AOSmithApiError as err:
                errors.append(err)
                continue
            devices = _extract_devices(data)
            if self._device_id:
                devices = [dev for dev in devices if dev.device_id == self._device_id]
            if devices:
                return devices

        if errors:
            raise AOSmithApiError("; ".join(str(err) for err in errors))
        return []

    async def async_get_realtime(self, device_id: str) -> dict[str, Any]:
        """Ask the cloud for realtime data if the endpoint is enabled."""

        return await self._request(
            "POST",
            ENDPOINT_REALTIME,
            json={"deviceId": device_id, **({"familyId": self._family_id} if self._family_id else {})},
        )

    async def async_invoke_method(
        self,
        device_id: str,
        method: str,
        params: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Invoke a device service through /device/invokeMethod."""

        params_dict = dict(params or {})
        if "payLoad" in params_dict:
            payload = params_dict
            payload.setdefault("deviceId", device_id)
            payload.setdefault("familyId", self._family_id or "")
            payload.setdefault("userId", self._user_id or "")
            payload.setdefault("currUserMobile", self._mobile or "")
            payload.setdefault("commandSource", 1)
            payload.setdefault("appSource", 2)
        else:
            self._validate_command_context(device_id)
            input_data = params_dict.pop("inputData", params_dict)
            payload = self._build_service_payload(
                device_id,
                method,
                input_data,
                product_type=str(params_dict.pop("productType", "24")),
                device_type=params_dict.pop("deviceType", None),
                invoke_channel=params_dict.pop("invokeChannel", None),
            )
        return await self._request("POST", ENDPOINT_INVOKE, json=payload)

    async def async_set_water_temperature(
        self,
        device_id: str,
        temperature: int | float,
        *,
        product_type: str = "24",
        device_type: str | None = None,
    ) -> dict[str, Any]:
        """Set domestic hot-water target temperature."""

        return await self.async_invoke_method(
            device_id,
            "SetTemperature",
            {
                "productType": product_type,
                "deviceType": device_type,
                "inputData": {
                    "CommandValue": str(int(temperature)),
                    "CommandType": "0",
                },
            },
        )

    async def async_set_heating_enabled(
        self,
        device_id: str,
        enabled: bool,
        *,
        product_type: str = "24",
        device_type: str | None = None,
    ) -> dict[str, Any]:
        """Turn the heating function on or off."""

        return await self.async_invoke_method(
            device_id,
            "SetHeatingOnOff",
            {
                "productType": product_type,
                "deviceType": device_type,
                "inputData": {"CommandValue": "1" if enabled else "0"},
            },
        )

    async def async_start_quick_wash(
        self,
        device_id: str,
        mode: str,
        *,
        product_type: str = "24",
        device_type: str | None = None,
    ) -> dict[str, Any]:
        """Start one-key or 24-hour quick wash."""

        if mode not in {"one_key", "24h"}:
            raise AOSmithApiError(f"unsupported quick wash mode: {mode}")
        return await self.async_invoke_method(
            device_id,
            "SetCruiseOnOff",
            {
                "productType": product_type,
                "deviceType": device_type,
                "invokeChannel": "0",
                "inputData": {"CommandValue": "1" if mode == "one_key" else "2"},
            },
        )

    async def async_stop_quick_wash(
        self,
        device_id: str,
        *,
        product_type: str = "24",
        device_type: str | None = None,
    ) -> dict[str, Any]:
        """Stop quick wash / cruise mode."""

        return await self.async_invoke_method(
            device_id,
            "SetCruiseOnOff",
            {
                "productType": product_type,
                "deviceType": device_type,
                "invokeChannel": "0",
                "inputData": {"CommandValue": "0"},
            },
        )

    def _build_service_payload(
        self,
        device_id: str,
        identifier: str,
        input_data: Mapping[str, Any],
        *,
        product_type: str = "24",
        device_type: str | None = None,
        invoke_channel: str | None = None,
    ) -> dict[str, Any]:
        """Build the nested payLoad format used by the Android app."""

        service: dict[str, Any] = {
            "identifier": identifier,
            "inputData": dict(input_data),
        }
        if invoke_channel is not None:
            service["invokeChannel"] = str(invoke_channel)
        service_payload = {
            "profile": {
                "deviceId": device_id,
                "productType": product_type,
                "deviceType": device_type or "",
            },
            "service": service,
        }
        return {
            "userId": self._user_id or "",
            "familyId": self._family_id or "",
            "deviceId": device_id,
            "currUserMobile": self._mobile or "",
            "commandSource": 1,
            "appSource": 2,
            "payLoad": jsonlib.dumps(service_payload, ensure_ascii=False, separators=(",", ":")),
        }

    def _validate_command_context(self, device_id: str) -> None:
        """Refuse to send app-style commands with missing identity fields."""

        missing = []
        if not self._user_id:
            missing.append("user_id")
        if not self._family_id:
            missing.append("family_id")
        if not device_id:
            missing.append("device_id")
        if not self._mobile:
            missing.append("mobile")
        if missing:
            raise AOSmithApiError(
                "Cannot send command because required config fields are missing: "
                + ", ".join(missing)
                + ". Delete and re-add the integration, or reconfigure it, and fill mobile/user_id/family_id/device_id."
            )

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: Mapping[str, Any] | None = None,
        auth: bool = True,
    ) -> dict[str, Any]:
        """Send a JSON request and normalize common response envelopes."""

        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json;charset=UTF-8",
            "User-Agent": "AOSmartHome/2.3.1 HomeAssistant/aosmith_ailink",
        }
        if auth and self._access_token:
            headers["Authorization"] = f"Bearer {self._access_token}"
            headers["accessToken"] = self._access_token
            headers["token"] = self._access_token

        url = f"{self._base_url}{path}"
        try:
            async with asyncio.timeout(self._timeout.total or 20):
                response = await self._session.request(
                    method,
                    url,
                    headers=headers,
                    json=dict(json or {}),
                    ssl=self._verify_ssl,
                    timeout=self._timeout,
                )
                text = await response.text()
                if response.status >= 400:
                    raise AOSmithApiError(f"{path} HTTP {response.status}")
                try:
                    data = await response.json(content_type=None)
                except ValueError as err:
                    raise AOSmithApiError(f"{path} returned non-JSON") from err
        except (TimeoutError, ClientError) as err:
            raise AOSmithApiError(f"{path} request failed ({type(err).__name__})") from err

        if not isinstance(data, dict):
            raise AOSmithApiError(f"{path} returned unexpected payload: {type(data).__name__}")

        code = _find_first(data, ("code", "status", "resultCode"))
        if code not in (None, 0, "0", 200, "200", True):
            raise AOSmithApiError(f"{path} returned an unsuccessful status")
        _LOGGER.debug("AILink %s request completed", path)
        return data


def _extract_devices(data: Mapping[str, Any]) -> list[AOSmithDevice]:
    """Find device-like dictionaries in a nested API response."""

    candidates: list[dict[str, Any]] = []

    def walk(value: Any) -> None:
        if isinstance(value, list):
            for item in value:
                walk(item)
            return
        if isinstance(value, dict):
            if _find_first(value, ("deviceId", "devId", "id", "g4Id")) and (
                _find_first(value, ("deviceName", "name", "productName", "modelName"))
                or _find_first(value, ("online", "isOnline", "netState"))
                or _find_first(value, ("productModel", "productMajorClassCode"))
                or isinstance(value.get("appDeviceStatusInfoEntity"), dict)
                or isinstance(value.get("statusInfo"), str)
            ):
                candidates.append(dict(value))
            for item in value.values():
                walk(item)

    walk(data.get("data", data))

    devices: dict[str, AOSmithDevice] = {}
    for raw in candidates:
        device_id = str(_find_first(raw, ("deviceId", "devId", "id", "g4Id")))
        merged_raw = _merge_status_payload(raw)
        name = str(_find_first(merged_raw, ("deviceName", "name", "productName", "nickName")) or device_id)
        model = _find_first(merged_raw, ("deviceModel", "model", "modelName", "productModel", "productName", "productId"))
        online_value = _find_first(raw, ("online", "isOnline", "netState", "status"))
        devices[device_id] = AOSmithDevice(
            device_id=device_id,
            name=name,
            model=str(model) if model is not None else None,
            online=_coerce_online(online_value),
            raw=merged_raw,
        )
    return list(devices.values())


def _merge_status_payload(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Flatten statusInfo.events[0].outputData into the raw device payload."""

    merged = dict(raw)
    status_info = raw.get("statusInfo")
    status_entity = raw.get("appDeviceStatusInfoEntity")
    if not status_info and isinstance(status_entity, Mapping):
        status_info = status_entity.get("statusInfo")
        merged.update({f"status_{key}": value for key, value in status_entity.items() if key != "statusInfo"})

    if isinstance(status_info, str) and status_info:
        try:
            status = jsonlib.loads(status_info)
        except ValueError:
            return merged
        profile = status.get("profile")
        if isinstance(profile, Mapping):
            merged.update({f"profile_{key}": value for key, value in profile.items()})
            for key, value in profile.items():
                merged.setdefault(key, value)
        events = status.get("events")
        if isinstance(events, list) and events:
            output_data = events[0].get("outputData") if isinstance(events[0], Mapping) else None
            if isinstance(output_data, Mapping):
                merged.update(output_data)
    return merged


def _find_first(data: Mapping[str, Any], keys: tuple[str, ...]) -> Any:
    """Return the first matching value, case-insensitively."""

    lowered = {str(key).lower(): value for key, value in data.items()}
    for key in keys:
        if key in data:
            return data[key]
        if key.lower() in lowered:
            return lowered[key.lower()]
    return None


def _coerce_online(value: Any) -> bool | None:
    """Coerce common online flags."""

    if value is None:
        return None
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "online", "on", "yes", "connected"}:
        return True
    if text in {"0", "false", "offline", "off", "no", "disconnected"}:
        return False
    return None
