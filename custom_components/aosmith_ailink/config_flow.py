"""Config flow for A. O. Smith AILink."""

from __future__ import annotations

from typing import Any

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_SCAN_INTERVAL, CONF_USERNAME
from homeassistant.core import callback
import voluptuous as vol

from .const import (
    CONF_ACCESS_TOKEN,
    CONF_BASE_URL,
    CONF_DEVICE_ID,
    CONF_FAMILY_ID,
    CONF_MOBILE,
    CONF_USER_ID,
    CONF_VERIFY_SSL,
    DEFAULT_BASE_URL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)


class AOSmithConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return AOSmithOptionsFlow(config_entry)

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Create a config entry."""

        errors: dict[str, str] = {}
        if user_input is not None:
            base_url = str(user_input[CONF_BASE_URL]).rstrip("/")
            if not base_url.startswith(("http://", "https://")):
                errors[CONF_BASE_URL] = "invalid_url"
            elif not (user_input.get(CONF_ACCESS_TOKEN) or user_input.get(CONF_USERNAME)):
                errors["base"] = "auth_required"
            else:
                if user_input.get(CONF_MOBILE) and not user_input.get(CONF_USERNAME):
                    user_input[CONF_USERNAME] = user_input[CONF_MOBILE]
                unique_id = f"aosmith_ailink_{user_input.get(CONF_DEVICE_ID) or base_url}"
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()
                user_input[CONF_BASE_URL] = base_url
                return self.async_create_entry(title="A. O. Smith AILink", data=user_input)

        schema = vol.Schema(
            {
                vol.Required(CONF_BASE_URL, default=DEFAULT_BASE_URL): str,
                vol.Optional(CONF_ACCESS_TOKEN): str,
                vol.Required(CONF_MOBILE): str,
                vol.Optional(CONF_USERNAME): str,
                vol.Optional(CONF_PASSWORD): str,
                vol.Required(CONF_USER_ID): str,
                vol.Required(CONF_FAMILY_ID): str,
                vol.Required(CONF_DEVICE_ID): str,
                vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): int,
                vol.Optional(CONF_VERIFY_SSL, default=True): bool,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)


class AOSmithOptionsFlow(config_entries.OptionsFlow):
    """Handle options for A. O. Smith AILink."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current_options = self.config_entry.options
        current_data = self.config_entry.data

        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_SCAN_INTERVAL,
                    default=current_options.get(
                        CONF_SCAN_INTERVAL,
                        current_data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                    ),
                ): int,
                vol.Optional(
                    CONF_ACCESS_TOKEN,
                    description={"suggested_value": current_options.get(CONF_ACCESS_TOKEN, current_data.get(CONF_ACCESS_TOKEN, ""))},
                ): str,
                vol.Optional(
                    CONF_VERIFY_SSL,
                    default=current_options.get(
                        CONF_VERIFY_SSL,
                        current_data.get(CONF_VERIFY_SSL, True),
                    ),
                ): bool,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
