"""Shared base entity."""
from __future__ import annotations

from homeassistant.const import CONF_HOST
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


class EpisodeEntity(CoordinatorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, key: str) -> None:
        super().__init__(coordinator)
        host = coordinator.entry.data[CONF_HOST]
        self._attr_unique_id = f"{DOMAIN}_{host}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, host)},
            name=coordinator.entry.title,
            manufacturer="Episode (Snap One)",
            model="EA-AMP-HYB-2D",
            configuration_url=f"http://{host}",
        )
