"""The Generic Hygrostat custom component integration."""
import logging
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.reload import async_setup_reload_service

_LOGGER = logging.getLogger(__name__)

DOMAIN = "generic_hygrostat"
PLATFORMS = ["binary_sensor"]

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
	"""Set up the Generic Hygrostat component from YAML."""
	
	# Registers the reload service and dynamically populates the Developer Tools UI
	await async_setup_reload_service(hass, DOMAIN, PLATFORMS)
	
	return True
