# Copyright (C) 2026 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License").
"""``akande server`` — start the CherryPy briefing server.

Exposes the same SSE / REST surface as picking option 3 from the
classic CLI menu, but as a foregrounded subcommand so external
processes (the Go TUI, smoke tests, container entrypoints) can
launch the server without driving the interactive prompt.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys


def server_command(
    args: argparse.Namespace,
) -> int:  # pragma: no cover - boots a real server
    from akande.__main__ import _build_akande

    try:
        akande = _build_akande()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(akande.run_server())
        host = getattr(args, "host", "127.0.0.1") or "127.0.0.1"
        port = getattr(args, "port", 8080) or 8080
        sys.stderr.write(
            f"akande server listening on http://{host}:{port}\n"
        )
        sys.stderr.flush()
        try:
            loop.run_forever()
        except KeyboardInterrupt:
            sys.stderr.write("\nakande server shutting down\n")
        finally:
            loop.run_until_complete(akande.stop_server())
            loop.close()
        return 0
    except Exception as exc:
        logging.error(
            "akande server failed: %s",
            exc,
            extra={"event": "Server:Failed"},
        )
        sys.stderr.write(f"akande server failed: {exc}\n")
        return 1
