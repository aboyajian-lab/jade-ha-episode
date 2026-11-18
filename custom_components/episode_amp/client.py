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


class EpisodeAuthError(EpisodeError):
    """Raised when the amplifier asks for a password and the one given is missing or wrong."""


@dataclass
class AmpState:
    volume_db: dict[int, float] = field(default_factory=dict)
    muted: dict[int, bool] = field(default_factory=dict)
    power_mode: int | None = None


class EpisodeClient:
    """Opens a short TCP connection per command (the amp is polled, not streamed)."""

    def __init__(self, host: str, port: int, mode: str = MODE_AUTO, password: str | None = None) -> None:
        self.host = host
        self.port = port
        self.mode = mode
        self.password = password or None
        self._lock = asyncio.Lock()

    @staticmethod
    async def _read(reader, writer, total: float, idle: float = IDLE_READ, until: tuple[str, ...] = ()) -> bytes:
        """Read until `total` seconds pass, the line goes quiet for `idle`, or a word in `until` appears."""
        data = bytearray()
        loop = asyncio.get_running_loop()
        deadline = loop.time() + total
        while True:
            remaining = deadline - loop.time()
            if remaining <= 0:
                break
            try:
                chunk = await asyncio.wait_for(reader.read(256), min(remaining, idle) if data else remaining)
            except asyncio.TimeoutError:
                break
            if not chunk:
                break
            data.extend(chunk)
            answer = p.telnet_refusals(chunk)
            if answer:
                writer.write(answer)
                await writer.drain()
            if until and p.mentions(bytes(data), *until):
                break
        return bytes(data)

    async def _login(self, reader, writer) -> None:
        """Handle the amp's telnet password prompt, if it shows one."""
        greeting = await self._read(reader, writer, 1.0, idle=0.6, until=("password",))
        if not p.mentions(greeting, "password"):
            # Some firmware only shows the prompt after the client sends something.
            writer.write(b"\r\n")
            await writer.drain()
            greeting += await self._read(reader, writer, 1.5, idle=0.6, until=("password",))
        if not p.mentions(greeting, "password"):
            return
        if not self.password:
            raise EpisodeAuthError("the amplifier asks for a password")
        writer.write(self.password.encode("utf-8") + b"\r\n")
        await writer.drain()
        after = await self._read(reader, writer, 1.5, idle=0.6)
        if p.mentions(after, "password", "incorrect", "invalid", "denied", "fail", "wrong"):
            raise EpisodeAuthError("the amplifier rejected the password")

    async def _exchange(self, payload: bytes, mode: str) -> bytes:
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port), CONNECT_TIMEOUT
            )
        except (OSError, asyncio.TimeoutError) as err:
            raise EpisodeError(f"cannot connect to {self.host}:{self.port}: {err}") from err
        try:
            await self._login(reader, writer)
            writer.write(p.to_text(payload) if mode == MODE_TEXT else payload)
            await writer.drain()
            data = await self._read(reader, writer, REPLY_TIMEOUT)
            _LOGGER.debug("%s raw reply %r", mode, data[:120])
            if p.mentions(data, "password"):
                raise EpisodeAuthError("the amplifier asks for a password")
            return p.decode_reply(data)
        except OSError as err:
            raise EpisodeError(f"connection to {self.host}:{self.port} dropped: {err}") from err
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
                try:
                    reply = await self._exchange(payload, mode)
                except EpisodeAuthError:
                    raise
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
