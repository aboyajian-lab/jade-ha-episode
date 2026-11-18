"""Read-only power mode (On / Auto / 12V trigger)."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .entity import EpisodeEntity

POWER_MODES = {0: "On", 1: "Auto", 2: "12V trigger"}


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities) -> None:
    async_add_entities([EpisodePowerMode(hass.data[DOMAIN][entry.entry_id])])


class EpisodePowerMode(EpisodeEntity, SensorEntity):
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_name = "Power mode"
    _attr_icon = "mdi:power"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "power_mode")

    @property
    def native_value(self) -> str | None:
        data = self.coordinator.data
        if not data or data.power_mode is None:
            return None
        return POWER_MODES.get(data.power_mode, str(data.power_mode))
