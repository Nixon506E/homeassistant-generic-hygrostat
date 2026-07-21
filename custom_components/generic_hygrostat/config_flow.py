"""Config flow for Generic Hygrostat Custom integration."""
from __future__ import annotations

from datetime import timedelta
from typing import Any
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers import selector

from .const import (
    DOMAIN,
    CONF_SENSOR,
    CONF_ATTRIBUTE,
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

    def __init__(self) -> None:
        """Initialize temporary configuration cache variables."""
        self._user_inputs: dict[str, Any] = {}

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Link the primary integration card to our options handler interface."""
        return GenericHygrostatOptionsFlowHandler()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial setup step triggered by the user interface."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._user_inputs.update(user_input)
            # Advance to the secondary configuration step
            return await self.async_step_attributes()

        data_schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default="Generic Hygrostat"): str,
                vol.Required(CONF_SENSOR): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor", device_class="humidity")
                ),
            }
        )
        
        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )

    async def async_step_attributes(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Render dynamic attribute selectors and variables."""
        errors: dict[str, str] = {}
    
        if user_input is not None:
            self._user_inputs.update(user_input)
            
            # Commit unique identifier tracking
            await self.async_set_unique_id(self._user_inputs[CONF_NAME].lower().replace(" ", "_"))
            self._abort_if_unique_id_configured()
    
            return self.async_create_entry(
                title=self._user_inputs[CONF_NAME], 
                data=self._user_inputs
            )
    
        # Pull the specific target sensor ID gathered from Step 1
        target_entity_id = self._user_inputs.get(CONF_SENSOR)
    
        data_schema = vol.Schema(
            {
                # This queries the sensor dynamically and generates an attribute picker list
                vol.Optional(CONF_ATTRIBUTE): selector.AttributeSelector(
                    selector.AttributeSelectorConfig(entity_id=target_entity_id)
                ),
                vol.Optional(CONF_DELTA_TRIGGER, default=3.0): vol.Coerce(float),
                vol.Optional(CONF_TARGET_OFFSET, default=3.0): vol.Coerce(float),
                vol.Optional(CONF_MIN_HUMIDITY, default=0.0): vol.Coerce(float),
                vol.Optional(CONF_MIN_ON_TIME, default={"hours": 0, "minutes": 0, "seconds": 0}): selector.DurationSelector(),
                vol.Optional(CONF_MAX_ON_TIME, default={"hours": 2, "minutes": 0, "seconds": 0}): selector.DurationSelector(),
                vol.Optional(CONF_SAMPLE_INTERVAL, default={"hours": 0, "minutes": 15, "seconds": 0}): selector.DurationSelector(),
            }
        )
    
        return self.async_show_form(step_id="attributes", data_schema=data_schema, errors=errors)

    async def async_step_import(self, import_config: dict[str, Any]) -> FlowResult:
        """Import legacy configurations safely."""
        unique_name = import_config.get(CONF_NAME, "Bathroom Hygrostat")
        unique_id = unique_name.lower().replace(" ", "_")
        
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()
        
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

class GenericHygrostatOptionsFlowHandler(config_entries.OptionsFlow):
    """💡 New class to handle updating existing runtime parameters via the UI."""
    
    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the configuration options panel form layout."""
        if user_input is not None:
            # Merges and saves the new configuration changes automatically
            return self.async_create_entry(title="", data=user_input)
    
        # Fetch current parameters to use them as pre-filled placeholders inside the UI
        # Check both entry.options and entry.data to catch values from creation step
        current_config = {**self.config_entry.data, **self.config_entry.options}
    
        options_schema = vol.Schema(
            {
                vol.Optional(CONF_DELTA_TRIGGER, default=current_config.get(CONF_DELTA_TRIGGER, 3.0)): vol.Coerce(float),
                vol.Optional(CONF_TARGET_OFFSET, default=current_config.get(CONF_TARGET_OFFSET, 3.0)): vol.Coerce(float),
                vol.Optional(CONF_MIN_HUMIDITY, default=current_config.get(CONF_MIN_HUMIDITY, 0.0)): vol.Coerce(float),
                vol.Optional(CONF_MIN_ON_TIME, default=current_config.get(CONF_MIN_ON_TIME, {"seconds": 0})): selector.DurationSelector(),
                vol.Optional(CONF_MAX_ON_TIME, default=current_config.get(CONF_MAX_ON_TIME, {"seconds": 7200})): selector.DurationSelector(),
                vol.Optional(CONF_SAMPLE_INTERVAL, default=current_config.get(CONF_SAMPLE_INTERVAL, {"seconds": 900})): selector.DurationSelector(),
            }
        )
    
        return self.async_show_form(step_id="init", data_schema=options_schema)
