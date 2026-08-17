#!/usr/bin/env python3
"""One-shot loopback server for the assembled TELNET client acceptance test."""

from __future__ import annotations

import argparse
from pathlib import Path
import socket


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("port_file", type=Path)
    parser.add_argument("port", type=int, nargs="?", default=23232)
    args = parser.parse_args()

    with socket.socket() as listener:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind(("127.0.0.1", args.port))
        listener.listen(1)
        args.port_file.write_text(str(listener.getsockname()[1]) + "\n")
        client, _ = listener.accept()
        with client:
            client.settimeout(15.0)
            client.sendall(b"REAL TELNET OK\r\n")
            try:
                while client.recv(1024):
                    pass
            except (ConnectionResetError, socket.timeout):
                pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
