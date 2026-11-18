"""Per-channel volume, in dB."""
from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .entity import EpisodeEntity
from .protocol import VOL_MAX_DB, VOL_MIN_DB


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(EpisodeVolume(coordinator, ch) for ch in (1, 2))


class EpisodeVolume(EpisodeEntity, NumberEntity):
    _attr_native_min_value = VOL_MIN_DB
    _attr_native_max_value = VOL_MAX_DB
    _attr_native_step = 0.5
    _attr_native_unit_of_measurement = "dB"
    _attr_mode = NumberMode.SLIDER
    _attr_icon = "mdi:volume-high"

    def __init__(self, coordinator, channel: int) -> None:
        super().__init__(coordinator, f"ch{channel}_volume")
        self._channel = channel
        self._attr_name = f"Channel {channel} volume"

    @property
    def native_value(self) -> float | None:
        data = self.coordinator.data
        return data.volume_db.get(self._channel) if data else None

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.client.set_volume(self._channel, value)
        data = self.coordinator.data
        if data:
            data.volume_db[self._channel] = round(float(value), 1)
            self.coordinator.async_set_updated_data(data)
