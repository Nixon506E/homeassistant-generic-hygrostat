"""Config flow for Generic Hygrostat Custom integration."""
from __future__ import annotations

from typing import Any
import voluptuous as vol
from datetime import timedelta

from homeassistant import config_entries
from homeassistant.const import CONF_NAME, CONF_ATTRIBUTE, CONF_UNIQUE_ID
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv

from .const import (
    DOMAIN,
    CONF_SENSOR,
    CONF_DELTA_TRIGGER,
    CONF_TARGET_OFFSET,
    CONF_MIN_HUMIDITY,
    CONF_MIN_ON_TIME,
    CONF_MAX_ON_TIME,
    CONF_SAMPLE_INTERVAL,
)

class GenericHygrostatConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Generic Hygrostat Custom."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial setup step triggered by the user interface."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Enforce a unique fallback identifier bound to the instance setup name
            await self.async_set_unique_id(user_input[CONF_NAME].lower().replace(" ", "_"))
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=user_input[CONF_NAME], 
                data=user_input
            )

        # Draw a form containing essential sensor fields
        data_schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default="Generic Hygrostat"): str,
                vol.Required(CONF_SENSOR): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain="sensor",
                        device_class=SensorDeviceClass.HUMIDITY,
                    )
                ),
                vol.Optional(CONF_ATTRIBUTE): str,
                vol.Optional(CONF_DELTA_TRIGGER, default=3.0): vol.Coerce(float),
                vol.Optional(CONF_TARGET_OFFSET, default=3.0): vol.Coerce(float),
                vol.Optional(CONF_MIN_ON_TIME, default={"hours": 0, "minutes": 0, "seconds": 0}): selector.DurationSelector(),
                vol.Optional(CONF_MAX_ON_TIME, default={"hours": 2, "minutes": 0, "seconds": 0}): selector.DurationSelector(),
                vol.Optional(CONF_SAMPLE_INTERVAL, default={"hours": 0, "minutes": 5, "seconds": 0}): selector.DurationSelector(),
                vol.Optional(CONF_MIN_HUMIDITY, default=0.0): vol.Coerce(float),
            }
        )

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )

    async def async_step_import(self, import_config: dict[str, Any]) -> FlowResult:
        """Import a legacy YAML configuration entry seamlessly into the UI."""
        # Generate a consistent unique ID based on the name to avoid duplicate imports
        unique_name = import_config.get(CONF_NAME, "Generic Hygrostat")
        unique_id = unique_name.lower().replace(" ", "_")
        
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()
        
        # Extract and format data coming from legacy configurations safely
        def _get_duration_dict(value: Any, default_seconds: int) -> dict[str, int]:
            seconds = default_seconds
            if isinstance(value, timedelta):
                seconds = int(value.total_seconds())
            elif isinstance(value, int):
                seconds = value
        
            return {
                "hours": seconds // 3600,
                "minutes": (seconds % 3600) // 60,
                "seconds": seconds % 60
            }
        
        formatted_input = {
            CONF_NAME: unique_name,
            CONF_SENSOR: import_config.get(CONF_SENSOR),
            CONF_ATTRIBUTE: import_config.get(CONF_ATTRIBUTE),
            CONF_DELTA_TRIGGER: import_config.get(CONF_DELTA_TRIGGER, 3.0),
            CONF_TARGET_OFFSET: import_config.get(CONF_TARGET_OFFSET, 3.0),
            CONF_MIN_HUMIDITY: import_config.get(CONF_MIN_HUMIDITY, 0.0),
            CONF_MIN_ON_TIME: _get_duration_dict(import_config.get(CONF_MIN_ON_TIME), 0),
            CONF_MAX_ON_TIME: _get_duration_dict(import_config.get(CONF_MAX_ON_TIME), 7200),
            CONF_SAMPLE_INTERVAL: _get_duration_dict(import_config.get(CONF_SAMPLE_INTERVAL), 900),
        }
        
        return self.async_create_entry(title=unique_name, data=formatted_input)
