"""Episode EA-AMP-HYB-2D frame encoding and decoding (no Home Assistant imports).

Frame: 0xFE, function, total length, params..., checksum (low byte of the sum
of every byte before it). Set commands are answered by 0x06 (OK) or 0x15 (error).
Over the network the amp's command sheet describes the same frames written as
hex text, e.g. "FE C2 04 C4"; raw bytes are supported as a fallback.
"""
from __future__ import annotations

import re

HEADER = 0xFE
ACK = 0x06
NACK = 0x15

GET_MUTE = 0xC0
GET_VOLUME = 0xC2
GET_POWER_MODE = 0xCE
GET_PRESET_NAME = 0xC9
SET_MUTE = 0xA0
SET_VOLUME = 0xA2

VOL_MIN_DB = -99.0
VOL_MAX_DB = 0.0

_HEX = set("0123456789abcdefABCDEF \r\n\t")


def checksum(data: bytes | list[int]) -> int:
    return sum(data) & 0xFF


def frame(function: int, *params: int) -> bytes:
    body = [HEADER, function, 3 + len(params) + 1, *params]
    return bytes(body + [checksum(body)])


def db_to_raw(db: float) -> int:
    db = max(VOL_MIN_DB, min(VOL_MAX_DB, float(db)))
    return int(round(db * 10)) + 990


def raw_to_db(raw: int) -> float:
    return round((raw - 990) / 10.0, 1)


def set_volume(channel_code: int, db: float) -> bytes:
    raw = db_to_raw(db)
    return frame(SET_VOLUME, channel_code, (raw >> 8) & 0xFF, raw & 0xFF)


def set_mute(channel_code: int, muted: bool) -> bytes:
    return frame(SET_MUTE, channel_code, 1 if muted else 0)


def get_volume() -> bytes:
    return frame(GET_VOLUME)


def get_mute() -> bytes:
    return frame(GET_MUTE)


def get_power_mode() -> bytes:
    return frame(GET_POWER_MODE)


def get_preset_name(bank: int) -> bytes:
    return frame(GET_PRESET_NAME, bank)


def to_text(data: bytes) -> bytes:
    return (" ".join(f"{b:02X}" for b in data) + "\r\n").encode("ascii")


def strip_telnet(data: bytes) -> bytes:
    """Remove telnet option negotiation (IAC WILL/WONT/DO/DONT x) from text replies."""
    out = bytearray()
    i = 0
    while i < len(data):
        if data[i] == 0xFF and i + 2 < len(data) and data[i + 1] in (0xFB, 0xFC, 0xFD, 0xFE):
            i += 3
            continue
        out.append(data[i])
        i += 1
    return bytes(out)


_TOKEN = re.compile(rb"(?<![0-9A-Za-z])[0-9A-Fa-f]{2}(?![0-9A-Za-z])")


def decode_reply(data: bytes) -> bytes:
    """Turn a reply (hex text, possibly with prompts around it, or raw bytes) into raw bytes."""
    if not data:
        return b""
    cleaned = strip_telnet(data)
    try:
        text = cleaned.decode("ascii")
    except UnicodeDecodeError:
        return data
    if text.strip() and set(text) <= _HEX:
        tokens = text.split()
        if all(len(t) % 2 == 0 for t in tokens):
            return bytes.fromhex("".join(tokens))
    tokens = _TOKEN.findall(cleaned)
    if tokens:
        return bytes.fromhex(b"".join(tokens).decode("ascii"))
    return data


def telnet_refusals(data: bytes) -> bytes:
    """Answer every IAC DO with WONT and every IAC WILL with DONT."""
    out = bytearray()
    for i in range(len(data) - 2):
        if data[i] == 0xFF and data[i + 1] == 0xFD:
            out += bytes([0xFF, 0xFC, data[i + 2]])
        elif data[i] == 0xFF and data[i + 1] == 0xFB:
            out += bytes([0xFF, 0xFE, data[i + 2]])
    return bytes(out)


def mentions(data: bytes, *words: str) -> bool:
    low = strip_telnet(data).decode("ascii", "ignore").lower()
    return any(w in low for w in words)


_ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def _tail(data: bytes) -> str:
    text = _ANSI.sub("", strip_telnet(data).decode("ascii", "ignore"))
    return text.lower().rstrip(" *\r\n\t\x00\xff")


def tail_prompt(data: bytes) -> str | None:
    """'login' or 'password' when the text ends on that prompt, else None."""
    low = _tail(data)
    if low.endswith(("password:", "password")):
        return "password"
    if low.endswith(("login:", "login", "username:", "user name:", "user:")):
        return "login"
    return None


def prompting(data: bytes) -> bool:
    """True when the text ends on a login or password prompt (asking, not reporting)."""
    return tail_prompt(data) is not None


def rejected(data: bytes) -> bool:
    """True when the amp's answer to a password says it was refused."""
    if prompting(data):
        return True
    return mentions(data, "incorrect", "invalid", "denied", "fail", "wrong", "error", "bad pass")


def find_frame(data: bytes, function: int) -> bytes | None:
    """Return the first complete, checksum-valid frame for `function` in data."""
    i = 0
    while i < len(data):
        if data[i] == HEADER and i + 2 < len(data) and data[i + 1] == function:
            length = data[i + 2]
            end = i + length
            if 4 <= length <= 64 and end <= len(data):
                chunk = data[i:end]
                if checksum(chunk[:-1]) == chunk[-1]:
                    return chunk
        i += 1
    return None


def parse_volume(data: bytes) -> tuple[float, float] | None:
    f = find_frame(data, GET_VOLUME)
    if not f or len(f) != 8:
        return None
    return raw_to_db((f[3] << 8) | f[4]), raw_to_db((f[5] << 8) | f[6])


def parse_mute(data: bytes) -> tuple[bool, bool] | None:
    f = find_frame(data, GET_MUTE)
    if not f or len(f) != 6:
        return None
    return bool(f[3]), bool(f[4])


def parse_power_mode(data: bytes) -> int | None:
    f = find_frame(data, GET_POWER_MODE)
    if not f or len(f) != 5:
        return None
    return f[3]


def parse_preset_name(data: bytes) -> str | None:
    f = find_frame(data, GET_PRESET_NAME)
    if not f or len(f) < 6:
        return None
    return bytes(b for b in f[4:-1] if 32 <= b < 127).decode("ascii").strip()


def is_ack(data: bytes) -> bool:
    return ACK in data and NACK not in data
