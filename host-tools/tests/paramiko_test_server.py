#!/usr/bin/env python3
import base64
import pathlib
import socket
import sys
import threading
import time

import paramiko


class Server(paramiko.ServerInterface):
    def __init__(self, allowed, auth_mode="publickey", password="secret"):
        self.allowed = allowed
        self.auth_mode = auth_mode
        self.password = password
        self.shell = threading.Event()
        self.resized = threading.Event()

    def check_auth_publickey(self, username, key):
        print("auth", username, key.get_name(), key == self.allowed,
              file=sys.stderr, flush=True)
        if (self.auth_mode == "publickey" and username == "test" and
                key == self.allowed):
            return paramiko.AUTH_SUCCESSFUL
        return paramiko.AUTH_FAILED

    def check_auth_password(self, username, password):
        print("auth", username, "password", password == self.password,
              file=sys.stderr, flush=True)
        if (self.auth_mode in ("password", "mixed") and username == "test" and
                password == self.password):
            return paramiko.AUTH_SUCCESSFUL
        return paramiko.AUTH_FAILED

    def get_allowed_auths(self, username):
        return "publickey,password" if self.auth_mode == "mixed" else \
            self.auth_mode

    def check_channel_request(self, kind, chanid):
        print("channel", kind, chanid, file=sys.stderr, flush=True)
        return paramiko.OPEN_SUCCEEDED if kind == "session" else \
            paramiko.OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED

    def check_channel_pty_request(self, channel, term, width, height,
                                  pixelwidth, pixelheight, modes):
        print("pty", term, width, height, file=sys.stderr, flush=True)
        return True

    def check_channel_shell_request(self, channel):
        print("shell", file=sys.stderr, flush=True)
        self.shell.set()
        return True

    def check_channel_window_change_request(self, channel, width, height,
                                            pixelwidth, pixelheight):
        print("resize", width, height, file=sys.stderr, flush=True)
        if width == 40 and height == 24:
            self.resized.set()
            return True
        return False


def load_public(path):
    fields = pathlib.Path(path).read_text().split()
    return paramiko.Ed25519Key(data=base64.b64decode(fields[1]))


def main():
    directory = pathlib.Path(sys.argv[1])
    port_file = pathlib.Path(sys.argv[2])
    requested_port = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    connection_count = int(sys.argv[4]) if len(sys.argv) > 4 else 2
    read_client = bool(int(sys.argv[5])) if len(sys.argv) > 5 else True
    expect_session = bool(int(sys.argv[6])) if len(sys.argv) > 6 else True
    auth_mode = sys.argv[7] if len(sys.argv) > 7 else "publickey"
    password = sys.argv[8] if len(sys.argv) > 8 else "secret"
    host_key = paramiko.RSAKey.from_private_key_file(str(directory / "host_rsa"))
    allowed = load_public(directory / "id_ed25519.pub")
    listener = socket.socket()
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(("127.0.0.1", requested_port))
    listener.listen(4)
    port_file.write_text(str(listener.getsockname()[1]))
    # First connection is rejected by the client's unknown-host callback;
    # the second persists trust and authenticates.
    for attempt in range(connection_count):
        client, _ = listener.accept()
        transport = paramiko.Transport(client)
        transport.add_server_key(host_key)
        server = Server(allowed, auth_mode, password)
        try:
            transport.start_server(server=server)
            channel = transport.accept(10 if expect_session else 3)
            if attempt == connection_count - 1 and expect_session:
                if channel is None or not server.shell.wait(10) or not \
                        server.resized.wait(10):
                    raise RuntimeError("shell channel not opened")
                channel.send(b"\x1b[2J\x1b[2;3HREAL SSH OK\r\n")
                if read_client:
                    channel.settimeout(5)
                    channel.recv(16)
                try:
                    channel.close()
                except EOFError:
                    pass
        except (EOFError, paramiko.SSHException):
            if attempt == connection_count - 1 and expect_session:
                raise
        finally:
            transport.close()
    listener.close()


if __name__ == "__main__":
    main()
