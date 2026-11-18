"""Config flow: host + port, verified by reading the amp's volume before saving."""
from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT

from .client import EpisodeClient, EpisodeError
from .const import CONF_MODE, DEFAULT_NAME, DEFAULT_PORT, DOMAIN, MODE_AUTO, MODES


class EpisodeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            await self.async_set_unique_id(host)
            self._abort_if_unique_id_configured()
            client = EpisodeClient(host, user_input[CONF_PORT], user_input[CONF_MODE])
            try:
                await client.get_state()
            except EpisodeError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title=user_input[CONF_NAME],
                    data={
                        CONF_HOST: host,
                        CONF_PORT: user_input[CONF_PORT],
                        CONF_MODE: client.mode,
                    },
                )
        schema = vol.Schema(
            {
                vol.Required(CONF_HOST): str,
                vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
                vol.Required(CONF_MODE, default=MODE_AUTO): vol.In(MODES),
                vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)
