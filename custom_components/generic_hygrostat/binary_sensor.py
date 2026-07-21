"""Platform for Generic Hygrostat binary sensor integration."""
from __future__ import annotations

from datetime import timedelta, datetime
from typing import Any
import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_ATTRIBUTE,
    CONF_NAME,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event

_LOGGER = logging.getLogger(__name__)

from .const import (
    CONF_SENSOR,
    CONF_DELTA_TRIGGER,
    CONF_TARGET_OFFSET,
    CONF_MIN_HUMIDITY,
    CONF_MIN_ON_TIME,
    CONF_MAX_ON_TIME,
    CONF_SAMPLE_INTERVAL,
)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Generic Hygrostat platform dynamically from a config flow."""
    config = entry.data

    name = config.get(CONF_NAME)
    sensor_id = config.get(CONF_SENSOR)
    attr = config.get(CONF_ATTRIBUTE)
    delta_trigger = config.get(CONF_DELTA_TRIGGER, 3.0)
    target_offset = config.get(CONF_TARGET_OFFSET, 3.0)
    min_on_time = cv.time_period_dict(config.get(CONF_MIN_ON_TIME, {"seconds": 0}))
    max_on_time = cv.time_period_dict(config.get(CONF_MAX_ON_TIME, {"seconds": 7200}))
    sample_interval = cv.time_period_dict(config.get(CONF_SAMPLE_INTERVAL, {"seconds": 900}))
    min_humidity = config.get(CONF_MIN_HUMIDITY, 0.0)
    unique_id = entry.entry_id

    hygrostat = GenericHygrostat(
        hass, name, sensor_id, attr, delta_trigger, target_offset,
        min_on_time, max_on_time, sample_interval, min_humidity, unique_id
    )

    async_add_entities([hygrostat], True)


class GenericHygrostat(BinarySensorEntity):
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

        # Clear target sensor trackers
        if self._async_unsub_state_changed is not None:
            self._async_unsub_state_changed()
            self._async_unsub_state_changed = None

    @callback
    def _async_update_sensor(self, state):
        """Analyze humidity changes internally."""
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
    def device_class(self) -> BinarySensorDeviceClass:
        """Enforce standard moisture categorization profile."""
        return BinarySensorDeviceClass.MOISTURE

    @property
    def unique_id(self):
        """Return the unique id of this hygrostat."""
        return self._unique_id

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return entity specific state attributes for the frontend."""
        current_humidity = self._history[-1]["value"] if self._history else None
        
        # Calculate the rising rate (current humidity minus the lowest point in the sample window)
        rising_rate = 0.0
        if self._history:
            relative_min = min(x["value"] for x in self._history)
            rising_rate = round(current_humidity - relative_min, 2)
        
        return {
            "current_humidity": current_humidity,
            "rising_rate": f"{rising_rate}%" if current_humidity is not None else None,
            "target_humidity": self._target_humidity,
            "last_state_change": self._last_state_change.isoformat() if self._last_state_change != datetime.min else None,
            "history_samples_count": len(self._history),
        }
