# Copyright (C) 2026 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License").
"""Coverage for the audio-processing helpers in akande.server.server.

Patches pydub + speech_recognition so the helpers run without
requiring real audio bytes or a real network speech endpoint.
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest


class TestConvertToWavBranches:
    def _patch_audio_segment(self, *, raise_on_call=False):
        """Patch AudioSegment so from_file returns a stub that exports."""

        class _Seg:
            def set_channels(self, n):
                return self

            def set_frame_rate(self, n):
                return self

            def export(self, path, format="wav"):
                Path = __import__("pathlib").Path
                Path(path).write_bytes(b"RIFFwav-content")

        stub = MagicMock()
        if raise_on_call:
            stub.from_file.side_effect = (
                __import__(
                    "pydub.exceptions",
                    fromlist=["CouldntDecodeError"],
                ).CouldntDecodeError("bad")
            )
        else:
            stub.from_file.return_value = _Seg()
        return stub

    def test_content_type_hint_branch(self):
        from akande.server.server import AkandeServer

        stub = self._patch_audio_segment()
        with patch(
            "akande.server.server.AudioSegment", stub
        ):
            path = AkandeServer.convert_to_wav(
                b"x" * 10, content_type="audio/webm"
            )
        assert path.endswith(".wav")
        os.unlink(path)

    def test_magic_byte_branch(self):
        from akande.server.server import AkandeServer

        stub = self._patch_audio_segment()
        with patch(
            "akande.server.server.AudioSegment", stub
        ):
            # Magic ID3 → mp3
            path = AkandeServer.convert_to_wav(
                b"ID3" + b"\x00" * 32, content_type=""
            )
        assert path.endswith(".wav")
        os.unlink(path)

    def test_brute_force_fallback(self):
        from akande.server.server import AkandeServer

        stub = self._patch_audio_segment()
        with patch(
            "akande.server.server.AudioSegment", stub
        ):
            path = AkandeServer.convert_to_wav(
                b"garbage-not-magic",
                content_type="",
            )
        # The brute-force loop tries multiple formats; with our
        # stub the first attempt succeeds.
        assert path.endswith(".wav")
        os.unlink(path)

    def test_all_formats_fail_raises(self):
        from akande.server.server import AkandeServer

        stub = self._patch_audio_segment(raise_on_call=True)
        with patch(
            "akande.server.server.AudioSegment", stub
        ):
            with pytest.raises(RuntimeError):
                AkandeServer.convert_to_wav(b"x")


class TestProcessAudio:
    def test_success(self, tmp_path):
        from akande.server.server import AkandeServer

        wav = tmp_path / "x.wav"
        wav.write_bytes(b"RIFF" + b"\x00" * 100)
        with patch(
            "akande.server.server._recognizer"
        ) as rec:
            rec.recognize_google.return_value = "hello"
            rec.record.return_value = "audio-data"
            with patch(
                "akande.server.server.sr.AudioFile"
            ) as af:
                af.return_value.__enter__.return_value = (
                    MagicMock()
                )
                out = AkandeServer.process_audio(str(wav))
        assert out["success"] is True
        assert out["text"] == "hello"

    def test_unknown_value_error(self, tmp_path):
        import speech_recognition as sr

        from akande.server.server import AkandeServer

        wav = tmp_path / "x.wav"
        wav.write_bytes(b"RIFF" + b"\x00" * 100)
        with patch(
            "akande.server.server._recognizer"
        ) as rec:
            rec.recognize_google.side_effect = (
                sr.UnknownValueError()
            )
            rec.record.return_value = "audio-data"
            with patch(
                "akande.server.server.sr.AudioFile"
            ) as af:
                af.return_value.__enter__.return_value = (
                    MagicMock()
                )
                out = AkandeServer.process_audio(str(wav))
        assert out["success"] is False
        assert "understood" in out["error"]

    def test_request_error(self, tmp_path):
        import speech_recognition as sr

        from akande.server.server import AkandeServer

        wav = tmp_path / "x.wav"
        wav.write_bytes(b"RIFF" + b"\x00" * 100)
        with patch(
            "akande.server.server._recognizer"
        ) as rec:
            rec.recognize_google.side_effect = (
                sr.RequestError("up")
            )
            rec.record.return_value = "audio-data"
            with patch(
                "akande.server.server.sr.AudioFile"
            ) as af:
                af.return_value.__enter__.return_value = (
                    MagicMock()
                )
                out = AkandeServer.process_audio(str(wav))
        assert out["success"] is False
        assert "service" in out["error"]
