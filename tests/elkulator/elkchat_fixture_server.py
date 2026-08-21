#!/usr/bin/env python3
"""Deterministic HTTP fixture for ElkChat over the Pi1MHz raw TCP service."""

from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs


PUBLIC_MESSAGES = (
    b'[{"rowid":101,"timestamp":"26-08-03 14:27",'
    b'"message":"lzI2LTA4LTAzIDE0OjI3IEFsaWNlOiAgICAgIJNIZWxsbyBmcm9tIENoYXQ2NCE=",'
    b'"regid":"DEMO","nickname":"Alice","lines":2,"pm":0,'
    b'"channel":"public"},'
    b'{"rowid":102,"timestamp":"26-08-03 14:28",'
    b'"message":"lzI2LTA4LTAzIDE0OjI4IEJvYjogICAgICAgIJRFbGtXaUZpIGlzIG9ubGluZS4=",'
    b'"regid":"DEMO","nickname":"Bob","lines":2,"pm":0,'
    b'"channel":"public"}]'
)

PRIVATE_MESSAGES = (
    b'[{"rowid":201,"timestamp":"26-08-03 14:29",'
    b'"message":"lzI2LTA4LTAzIDE0OjI5IEFsaWNlOiAgICAgIJVAYm9idGhlaW1wIFByaXZhdGUgaGVsbG8h",'
    b'"regid":"DEMO","nickname":"Alice","lines":2,"pm":0,'
    b'"channel":"private"}]'
)

USERS = (
    b"\x16\x04\x01\x10\x04\x13\x01Alice"
    b"\x16\x05\x01\x10\x04\x13\x01Eliza"
    b"\x16\x06\x01\x10\x07\x13\x82Bob\n\n"
)


class ElkChatFixtureHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"

    def log_message(self, format: str, *args: object) -> None:
        return

    def do_GET(self) -> None:  # noqa: N802, required by BaseHTTPRequestHandler
        self._respond(self._body({}))

    def do_POST(self) -> None:  # noqa: N802, required by BaseHTTPRequestHandler
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self.send_error(400)
            return
        if length < 0 or length > 4096:
            self.send_error(413)
            return
        fields = parse_qs(
            self.rfile.read(length).decode("ascii", errors="replace"),
            keep_blank_values=True,
        )
        self._respond(self._body(fields))

    def _body(self, fields: dict[str, list[str]]) -> bytes:
        endpoint = self.path.rsplit("/", 1)[-1].split("?", 1)[0]
        if endpoint == "connectivity.php":
            return b"Connected"
        if endpoint == "getRegistration.php":
            return b"r100"
        if endpoint == "zxReadAllMessages.php":
            if fields.get("type", ["public"])[0] == "private":
                cursor = fields.get("lastprivate", ["0"])[0]
                return b"[]" if cursor == "201" else PRIVATE_MESSAGES
            cursor = fields.get("lastmessage", ["0"])[0]
            return b"[]" if cursor == "102" else PUBLIC_MESSAGES
        if endpoint == "zxListUsers.php":
            return USERS if fields.get("page", ["0"])[0] == "0" else b"\n\n"
        if endpoint == "insertMessage.php":
            return b"0"
        return b"Not Found"

    def _respond(self, body: bytes) -> None:
        status = 404 if body == b"Not Found" else 200
        self.send_response(status)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()
    ThreadingHTTPServer((args.host, args.port), ElkChatFixtureHandler).serve_forever()


if __name__ == "__main__":
    main()
