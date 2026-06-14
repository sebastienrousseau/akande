# Copyright (C) 2026 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License").
"""Model Context Protocol (MCP) integration.

Two surfaces:

- :mod:`akande.mcp.server` — exposes Àkàndé's tools (briefing,
  watermark verify, audit verify, ConversationStore queries) as an
  MCP server that Claude Desktop / Cursor / Continue / Smithery
  can connect to.
- :mod:`akande.mcp.client` — consumes external MCP servers
  declared in ``~/.akande/mcp.json`` (Claude Desktop's schema) so
  Àkàndé itself can use upstream tools.

The ``mcp`` SDK is an *optional* dependency
(``pip install akande[mcp]``).  Without it, both modules import
fine but raise a clear error when the operator tries to run them
— never a silent failure.
"""

__all__ = ["server", "client"]
