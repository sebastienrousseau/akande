# Platform Support Matrix

## Supported platforms

| Platform | Audio input | Audio output (gTTS) | Audio output (pyttsx4) | Web server | Status |
|----------|-------------|---------------------|------------------------|------------|--------|
| macOS 13+ (ARM/Intel) | Yes | Yes | Yes | Yes | Fully supported |
| Ubuntu 22.04+ / Debian 12+ | Yes | Yes | Yes | Yes | Fully supported |
| Fedora 38+ | Yes | Yes | Yes | Yes | Fully supported |
| WSL2 (Ubuntu) | Limited | Limited | Limited | Yes | Partial support |
| Windows (native) | Untested | Untested | Yes | Yes | Community only |

## System dependencies

### macOS

```bash
brew install portaudio ffmpeg
```

### Ubuntu / Debian

```bash
sudo apt-get install portaudio19-dev ffmpeg libespeak-dev
```

### Fedora

```bash
sudo dnf install portaudio-devel ffmpeg espeak-ng-devel
```

### WSL2

WSL2 does not expose audio hardware by default. To enable audio:

1. Install PulseAudio on Windows and configure the TCP module.
2. Inside WSL2, set `PULSE_SERVER=tcp:$(hostname).local` before running Akande.
3. Install the same system dependencies as Ubuntu.

## Acceptance criteria

- `python -m akande --classic` launches without import errors.
- Text question flow (menu option 2) returns an LLM response.
- Voice input (menu option 1) captures audio and returns a transcript (requires working microphone).
- TTS plays audio through speakers (requires working audio output).
- Web server (menu option 3) serves the UI on `http://127.0.0.1:8080`.
- TUI mode (`python -m akande`) renders correctly in a terminal with 80+ columns.

## Known limitations

- **WSL2 audio**: Requires a PulseAudio bridge to the Windows host. Without it, TTS and STT will fail gracefully but the text and server flows remain functional.
- **pyttsx4 on Linux**: Requires `espeak-ng` or `espeak` to be installed as the speech backend.
- **PyAudio on ARM Linux**: May require building from source if no wheel is available.
