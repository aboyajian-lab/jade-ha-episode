"""Per-channel mute."""
from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .entity import EpisodeEntity


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(EpisodeMute(coordinator, ch) for ch in (1, 2))


class EpisodeMute(EpisodeEntity, SwitchEntity):
    _attr_icon = "mdi:volume-off"

    def __init__(self, coordinator, channel: int) -> None:
        super().__init__(coordinator, f"ch{channel}_mute")
        self._channel = channel
        self._attr_name = f"Channel {channel} mute"

    @property
    def is_on(self) -> bool | None:
        data = self.coordinator.data
        return data.muted.get(self._channel) if data else None

    async def async_turn_on(self, **kwargs) -> None:
        await self._set(True)

    async def async_turn_off(self, **kwargs) -> None:
        await self._set(False)

    async def _set(self, muted: bool) -> None:
        await self.coordinator.client.set_mute(self._channel, muted)
        data = self.coordinator.data
        if data:
            data.muted[self._channel] = muted
            self.coordinator.async_set_updated_data(data)
