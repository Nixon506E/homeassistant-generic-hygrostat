"""
Adds support for generic hygrostat units.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.generic_hygrostat/
"""
from __future__ import annotations

from datetime import timedelta, datetime
import logging

import voluptuous as vol

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_MOISTURE,
    PLATFORM_SCHEMA,
    BinarySensorEntity,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_ATTRIBUTE,
    CONF_NAME,
    CONF_SENSOR,
    CONF_UNIQUE_ID,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import (
    async_track_point_in_time,
    async_track_state_change_event,
)
from homeassistant.helpers.reload import async_setup_reload_service
from homeassistant.helpers.typing import Any, ConfigType, DiscoveryInfoType

from . import DOMAIN, PLATFORMS

_LOGGER = logging.getLogger(__name__)

CONF_DELTA_TRIGGER = "delta_trigger"
CONF_TARGET_OFFSET = "target_offset"
CONF_MIN_ON_TIME = "min_on_time"
CONF_MAX_ON_TIME = "max_on_time"
CONF_SAMPLE_INTERVAL = "sample_interval"
CONF_MIN_HUMIDITY = "min_humidity"

DEFAULT_NAME = "Generic Hygrostat"
DEFAULT_DELTA_TRIGGER = 3.0
DEFAULT_TARGET_OFFSET = 3.0
DEFAULT_MIN_ON_TIME = timedelta(seconds=0)
DEFAULT_MAX_ON_TIME = timedelta(seconds=7200)
DEFAULT_SAMPLE_INTERVAL = timedelta(minutes=5)
DEFAULT_MIN_HUMIDITY = 0.0

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_SENSOR): cv.entity_id,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_ATTRIBUTE): cv.string,
        vol.Optional(CONF_DELTA_TRIGGER, default=DEFAULT_DELTA_TRIGGER): vol.Coerce(float),
        vol.Optional(CONF_TARGET_OFFSET, default=DEFAULT_TARGET_OFFSET): vol.Coerce(float),
        vol.Optional(CONF_MIN_ON_TIME, default=DEFAULT_MIN_ON_TIME): cv.time_period,
        vol.Optional(CONF_MAX_ON_TIME, default=DEFAULT_MAX_ON_TIME): cv.time_period,
        vol.Optional(CONF_SAMPLE_INTERVAL, default=DEFAULT_SAMPLE_INTERVAL): cv.time_period,
        vol.Optional(CONF_MIN_HUMIDITY, default=DEFAULT_MIN_HUMIDITY): vol.Coerce(float),
        vol.Optional(CONF_UNIQUE_ID): cv.string,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Generic Hygrostat platform and link reload hooks."""
    
    # Hooks platform directly into the dynamic YAML reload layout
    await async_setup_reload_service(hass, DOMAIN, PLATFORMS)

    name = config.get(CONF_NAME)
    sensor_id = config.get(CONF_SENSOR)
    attr = config.get(CONF_ATTRIBUTE)
    delta_trigger = config.get(CONF_DELTA_TRIGGER)
    target_offset = config.get(CONF_TARGET_OFFSET)
    min_on_time = config.get(CONF_MIN_ON_TIME)
    max_on_time = config.get(CONF_MAX_ON_TIME)
    sample_interval = config.get(CONF_SAMPLE_INTERVAL)
    min_humidity = config.get(CONF_MIN_HUMIDITY)
    unique_id = config.get(CONF_UNIQUE_ID)

    hygrostat = GenericHygrostat(
        hass,
        name,
        sensor_id,
        attr,
        delta_trigger,
        target_offset,
        min_on_time,
        max_on_time,
        sample_interval,
        min_humidity,
        unique_id,
    )

    async_add_entities([hygrostat], True)


class GenericHygrostat(Entity):
    """Representation of a Generic Hygrostat device."""

    def __init__(
        self,
        hass,
        name,
        sensor_id,
        attr,
        delta_trigger,
        target_offset,
        min_on_time,
        max_on_time,
        sample_interval,
        min_humidity,
        unique_id,
    ):
        """Initialize the hygrostat sensor."""
        self.hass = hass
        self._name = name
        self._sensor_id = sensor_id
        self._attr = attr
        self._delta_trigger = delta_trigger
        self._target_offset = target_offset
        self._min_on_time = min_on_time
        self._max_on_time = max_on_time
        self._sample_interval = sample_interval
        self._min_humidity = min_humidity
        self._unique_id = unique_id
        
        self._state = False
        self._history = []
        self._target_humidity = None
        self._last_state_change = datetime.min
        
        # Track active background references safely
        self._remove_update_interval = None
        self._async_unsub_state_changed = None

    async def async_added_to_hass(self):
        """Run when entity is newly generated or tracked by Home Assistant."""

        @callback
        def _async_state_changed_listener(event):
            """Handle background tracking updates cleanly."""
            new_state = event.data.get("new_state")
            if new_state is None or new_state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
                return
            self._async_update_sensor(new_state)

        # Properly assign state changes to an unbindable property routine
        self._async_unsub_state_changed = async_track_state_change_event(
            self.hass, [self._sensor_id], _async_state_changed_listener
        )

        # Establish early initial state
        initial_state = self.hass.states.get(self._sensor_id)
        if initial_state and initial_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            self._async_update_sensor(initial_state)

    async def async_will_remove_from_hass(self):
        """Run when entity will be removed during YAML reloading."""

        # Clear out the timing loop
        if self._remove_update_interval is not None:
            self._remove_update_interval()
            self._remove_update_interval = None

        # Add this to clear target sensor trackers (if implemented in added_to_hass)
        if self._async_unsub_state_changed is not None:
            self._async_unsub_state_changed()
            self._async_unsub_state_changed = None

    @callback
    def _async_update_sensor(self, state):
        """Analyze humidity changes internally (Original Repository Logic)."""
        try:
            if self._attr:
                current_humidity = float(state.attributes.get(self._attr))
            else:
                current_humidity = float(state.state)
        except (ValueError, TypeError):
            return

        now = datetime.now()
        self._history = [x for x in self._history if now - x["time"] <= self._sample_interval]
        
        if current_humidity < self._min_humidity:
            self._history.clear()
            self._target_humidity = None
            if self._state:
                self._state = False
                self._last_state_change = now
                self.async_write_ha_state()
            return
        
        if not self._history:
            self._target_humidity = current_humidity + self._target_offset
        
        self._history.append({"time": now, "value": current_humidity})

        # Core conditional checks 
        if self._state:
            if current_humidity <= self._target_humidity or (now - self._last_state_change >= self._max_on_time):
                self._state = False
                self._last_state_change = now
                self._target_humidity = current_humidity + self._target_offset
        else:
            relative_min = min(x["value"] for x in self._history)
            if (current_humidity - relative_min >= self._delta_trigger) and (now - self._last_state_change >= self._min_on_time):
                self._state = True
                self._last_state_change = now

        self.async_write_ha_state()

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def is_on(self):
        """Return binary condition status."""
        return self._state
    
    @property
    def device_class(self):
        """Enforce standard moisture categorization profile."""
        return DEVICE_CLASS_MOISTURE

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return entity specific state attributes for the frontend."""
        return {
            "target_humidity": self._target_humidity,
            "last_state_change": self._last_state_change.isoformat() if self._last_state_change != datetime.min else None,
            "sample_interval": str(self._sample_interval),
            "history_samples_count": len(self._history),
        }

    @property
    def unique_id(self):
        """Return the unique id of this hygrostat."""
        return self._unique_id
