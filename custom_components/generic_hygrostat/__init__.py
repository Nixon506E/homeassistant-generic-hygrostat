"""The Generic Hygrostat custom component integration."""
from __future__ import annotations

import asyncio
import importlib
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.issue_registry import async_create_issue, IssueSeverity

from .const import DOMAIN, PLATFORMS

_LOGGER = logging.getLogger(__name__)

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Generic Hygrostat Custom from legacy YAML configuration."""
    try:
        await asyncio.gather(
            hass.async_add_executor_job(
                importlib.import_module, f"custom_components.{DOMAIN}.binary_sensor"
            ),
            hass.async_add_executor_job(
                importlib.import_module, f"custom_components.{DOMAIN}.config_flow"
            ),
        )
    except Exception as err: # pylint: disable=broad-except
        _LOGGER.error("Failed to pre-cache integration platforms: %s", err)
    
    if "binary_sensor" in config:
        yaml_detected = False
        for platform_config in config["binary_sensor"]:
            if platform_config.get("platform") == DOMAIN:
                yaml_detected = True
                # Forward configuration parameters to the automated config flow import sequence
                hass.async_create_task(
                    hass.config_entries.flow.async_init(
                        DOMAIN,
                        context={"source": "import"},
                        data=platform_config,
                    )
                )

        # If legacy lines were found and processed, generate a persistent Repair Issue
        if yaml_detected:
            async_create_issue(
                hass,
                DOMAIN,
                "deprecated_yaml",
                is_fixable=False,
                severity=IssueSeverity.WARNING,
                translation_key="deprecated_yaml",
            )
            _LOGGER.warning("Legacy YAML configuration detected for %s. Migrating to UI.", DOMAIN)

    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Generic Hygrostat Custom from a config entry setup wrapper."""
    # Instantiates the underlying platform asynchronously without blocking operations
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry dynamically when deleted or reloaded by user."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
