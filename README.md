# Episode hybrid amplifier for Home Assistant

Custom integration for the Episode EA-AMP-HYB-2D-1000 / -2000 amplifier, written for The Jade Winter Haven courtyard.

What it gives you, per channel:
- **Volume** slider in dB (-99 to 0), read back from the amp every 30 seconds
- **Mute** switch
- **Power mode** (On / Auto / 12V trigger), read only

It deliberately does not change presets, routing or speaker tuning.

## Protocol
Episode's control sheet: frames `FE <function> <length> <params…> <checksum>`, sent over the network as hex text (e.g. `FE C2 04 C4`). The client tries hex text first and falls back to raw bytes ("auto"), then remembers what worked. Set commands are answered with `06` (OK) or `15` (error).

## Install without host access
1. Add the built-in **Downloader** integration with folder `custom_components`.
2. Call `downloader.download_file` for each file in `custom_components/episode_amp/` with `subdir: episode_amp` (and `episode_amp/translations` for `en.json`).
3. Restart Home Assistant, then add **Episode Hybrid Amplifier**: IP, port 23, and the same user name and password as the amp's web page (its telnet server asks "Login:" then "Password:"). Setup logs in and reads the volume before saving, so a wrong port or login is caught.
4. Remove Downloader.
