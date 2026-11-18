"""Network client for the Episode hybrid amplifier."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field

from . import protocol as p
from .const import CHANNELS, MODE_AUTO, MODE_RAW, MODE_TEXT

_LOGGER = logging.getLogger(__name__)

CONNECT_TIMEOUT = 4.0
REPLY_TIMEOUT = 1.5
IDLE_READ = 0.25


class EpisodeError(Exception):
    """Raised when the amplifier cannot be reached or does not answer."""


@dataclass
class AmpState:
    volume_db: dict[int, float] = field(default_factory=dict)
    muted: dict[int, bool] = field(default_factory=dict)
    power_mode: int | None = None


class EpisodeClient:
    """Opens a short TCP connection per command (the amp is polled, not streamed)."""

    def __init__(self, host: str, port: int, mode: str = MODE_AUTO) -> None:
        self.host = host
        self.port = port
        self.mode = mode
        self._lock = asyncio.Lock()

    async def _exchange(self, payload: bytes, mode: str) -> bytes:
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port), CONNECT_TIMEOUT
            )
        except (OSError, asyncio.TimeoutError) as err:
            raise EpisodeError(f"cannot connect to {self.host}:{self.port}: {err}") from err
        try:
            # Let any banner or telnet negotiation arrive and discard it.
            try:
                await asyncio.wait_for(reader.read(256), IDLE_READ)
            except asyncio.TimeoutError:
                pass
            writer.write(p.to_text(payload) if mode == MODE_TEXT else payload)
            await writer.drain()
            data = bytearray()
            deadline = asyncio.get_running_loop().time() + REPLY_TIMEOUT
            while True:
                remaining = deadline - asyncio.get_running_loop().time()
                if remaining <= 0:
                    break
                try:
                    chunk = await asyncio.wait_for(
                        reader.read(256), min(remaining, IDLE_READ if data else remaining)
                    )
                except asyncio.TimeoutError:
                    break
                if not chunk:
                    break
                data.extend(chunk)
            return p.decode_reply(bytes(data))
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except OSError:
                pass

    async def _request(self, payload: bytes, accept) -> bytes:
        """Send a frame; return the decoded reply that `accept` approves."""
        async with self._lock:
            modes = [self.mode] if self.mode != MODE_AUTO else [MODE_TEXT, MODE_RAW]
            last = b""
            for mode in modes:
                reply = await self._exchange(payload, mode)
                _LOGGER.debug("%s %s -> %s", mode, payload.hex(" "), reply.hex(" "))
                if accept(reply):
                    if self.mode == MODE_AUTO:
                        self.mode = mode
                        _LOGGER.info("Episode amp at %s answers in %s mode", self.host, mode)
                    return reply
                last = reply
                await asyncio.sleep(0.2)
            raise EpisodeError(f"no valid reply to {payload.hex(' ')} (got {last.hex(' ') or 'nothing'})")

    async def get_state(self) -> AmpState:
        state = AmpState()
        vol = p.parse_volume(await self._request(p.get_volume(), lambda r: p.parse_volume(r) is not None))
        state.volume_db = {1: vol[0], 2: vol[1]}
        mute = p.parse_mute(await self._request(p.get_mute(), lambda r: p.parse_mute(r) is not None))
        state.muted = {1: mute[0], 2: mute[1]}
        try:
            state.power_mode = p.parse_power_mode(
                await self._request(p.get_power_mode(), lambda r: p.parse_power_mode(r) is not None)
            )
        except EpisodeError:
            state.power_mode = None
        return state

    async def set_volume(self, channel: int, db: float) -> None:
        await self._request(p.set_volume(CHANNELS[channel], db), p.is_ack)

    async def set_mute(self, channel: int, muted: bool) -> None:
        await self._request(p.set_mute(CHANNELS[channel], muted), p.is_ack)
