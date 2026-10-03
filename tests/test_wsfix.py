"""The whole-frame websocket write, against a socket that writes short.

This is the bug that broke the deployed instance while every test passed: a
multi-megabyte frame went out with one socket.send(), which wrote the first
couple of megabytes and reported as much, and simple-websocket threw that
number away. The browser read the next frame's payload where a header should
have been and closed the connection.

A real socket only does that when its send buffer is full, which on loopback
takes more than the suite will ever push through it, so the fake socket here
does it on purpose. That makes the test deterministic and fast; the price is
that it tests the write, not the network, and tests/browser/ has to cover the
rest.
"""

import pytest

from wsfix import apply_whole_frame_writes

simple_websocket_ws = pytest.importorskip("simple_websocket.ws")


class ShortWritingSocket:
    """Writes at most `chunk` bytes per send(), like a full send buffer."""

    def __init__(self, chunk=4096):
        self.chunk = chunk
        self.written = bytearray()
        self.send_calls = 0
        self.sendall_calls = 0

    def send(self, data):
        self.send_calls += 1
        taken = data[: self.chunk]
        self.written += taken
        return len(taken)

    def sendall(self, data):
        self.sendall_calls += 1
        self.written += data
        return None


class FakeWsproto:
    """Stands in for the wsproto connection, returning the bytes to write."""

    def __init__(self, payload):
        self.payload = payload

    def send(self, event):
        return self.payload


def make_connection(payload, chunk=4096):
    """A simple-websocket Base with its socket and framing replaced.

    Base.__init__ performs a handshake, so the object is built without it and
    only the two attributes send() touches are set.
    """
    connection = simple_websocket_ws.Base.__new__(simple_websocket_ws.Base)
    connection.connected = True
    connection.sock = ShortWritingSocket(chunk=chunk)
    connection.ws = FakeWsproto(payload)
    return connection


class TestWithoutThePatch:
    """What the library does on its own, so the test below means something."""

    def test_a_long_frame_is_truncated(self):
        """One short write, and the rest of the frame is gone.

        If this ever fails, simple-websocket has started looping and
        wsfix.py can be deleted -- which is the outcome to hope for.
        """
        frame = b"x" * (1024 * 1024)
        apply_whole_frame_writes()
        unpatched = simple_websocket_ws.Base.send.__wrapped__
        connection = make_connection(frame)

        unpatched(connection, "ignored")

        assert len(connection.sock.written) == 4096
        assert connection.sock.send_calls == 1


class TestWithThePatch:
    def test_the_whole_frame_is_written(self):
        frame = b"y" * (7 * 1024 * 1024)
        apply_whole_frame_writes()
        connection = make_connection(frame)

        simple_websocket_ws.Base.send(connection, "ignored")

        assert bytes(connection.sock.written) == frame
        assert connection.sock.sendall_calls == 1
        assert connection.sock.send_calls == 0

    def test_a_short_frame_is_unharmed(self):
        frame = b"z" * 12
        apply_whole_frame_writes()
        connection = make_connection(frame)

        simple_websocket_ws.Base.send(connection, "ignored")

        assert bytes(connection.sock.written) == frame

    def test_applying_it_twice_does_not_stack_wrappers(self):
        apply_whole_frame_writes()
        once = simple_websocket_ws.Base.send
        apply_whole_frame_writes()
        assert simple_websocket_ws.Base.send is once

    def test_the_socket_is_otherwise_untouched(self):
        """Everything but send() has to reach the real socket.

        receive() and close() go through the same attribute, so a wrapper that
        swallowed anything else would break reading rather than writing.
        """
        apply_whole_frame_writes()
        connection = make_connection(b"q" * 32)
        simple_websocket_ws.Base.send(connection, "ignored")

        wrapper = connection.sock
        assert wrapper.chunk == 4096
        assert wrapper.sendall_calls == 1
        wrapper.chunk = 17
        assert wrapper.chunk == 17
