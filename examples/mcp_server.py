# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Model Context Protocol (MCP) server example for Àkàndé."""

import sys


def main() -> None:
    try:
        from akande.mcp.server import serve
    except ImportError as exc:
        print(
            f"MCP dependency missing: {exc}\n"
            "Please install akande with the [mcp] extra: pip install 'akande[mcp]'"
        )
        sys.exit(1)

    print("Starting Àkàndé MCP server on stdio...")
    serve(stdio=True)


if __name__ == "__main__":
    main()
