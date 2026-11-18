"""Constants for the Episode hybrid amplifier integration."""

DOMAIN = "episode_amp"

CONF_MODE = "mode"
MODE_AUTO = "auto"
MODE_TEXT = "text"
MODE_RAW = "raw"
MODES = [MODE_AUTO, MODE_TEXT, MODE_RAW]

DEFAULT_PORT = 23
DEFAULT_NAME = "Episode Amp"
SCAN_INTERVAL_SECONDS = 30

CHANNELS = {1: 0xC2, 2: 0xC3}
