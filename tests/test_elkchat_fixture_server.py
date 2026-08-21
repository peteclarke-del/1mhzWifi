import http.client
import threading
import unittest
from urllib.parse import urlencode

from tests.elkulator.elkchat_fixture_server import (
    ElkChatFixtureHandler,
    ThreadingHTTPServer,
)


class ElkChatFixtureServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), ElkChatFixtureHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def post(self, endpoint: str, fields: dict[str, str]) -> bytes:
        connection = http.client.HTTPConnection(
            "127.0.0.1", self.server.server_port, timeout=2,
        )
        body = urlencode(fields)
        connection.request(
            "POST", f"/{endpoint}", body,
            {"Content-Type": "application/x-www-form-urlencoded"},
        )
        response = connection.getresponse()
        payload = response.read()
        self.assertEqual(response.status, 200)
        connection.close()
        return payload

    def test_public_and_private_responses_are_distinct(self):
        public = self.post("zxReadAllMessages.php", {"type": "public"})
        private = self.post("zxReadAllMessages.php", {"type": "private"})
        self.assertIn(b'"channel":"public"', public)
        self.assertNotIn(b'"channel":"private"', public)
        self.assertIn(b'"channel":"private"', private)

    def test_saved_cursor_returns_an_empty_page(self):
        self.assertEqual(
            self.post(
                "zxReadAllMessages.php",
                {"type": "public", "lastmessage": "102"},
            ),
            b"[]",
        )

    def test_user_list_uses_the_expected_control_bytes(self):
        users = self.post("zxListUsers.php", {"page": "0"})
        self.assertIn(b"\x10\x04\x13\x01Alice", users)
        self.assertIn(b"\x10\x07\x13\x82Bob", users)


if __name__ == "__main__":
    unittest.main()
