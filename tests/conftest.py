"""Shared fixtures.

Importing mudfinder has side effects: it creates saves/, registers an atexit
handler, and starts the savegame background thread. That is fine for tests --
the thread sleeps 300 seconds before doing anything -- but it does mean the
module-level ROOMS dict is shared state, so every test cleans up after itself.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import mudfinder  # noqa: E402
from player import Player  # noqa: E402
from session import Session  # noqa: E402
from unit import Unit  # noqa: E402

GM_KEY = "test-gm-key"


@pytest.fixture(autouse=True)
def clean_rooms():
    """Keep ROOMS empty between tests so rooms can't leak across them."""
    mudfinder.ROOMS.clear()
    yield
    mudfinder.ROOMS.clear()


@pytest.fixture
def app():
    mudfinder.app.config["TESTING"] = True
    # TESTING alone would re-raise inside the view, so the tests could only
    # assert on tracebacks. Turning propagation off lets them assert on the
    # status codes a browser would actually receive.
    mudfinder.app.config["PROPAGATE_EXCEPTIONS"] = False
    return mudfinder.app


@pytest.fixture
def http(app):
    return app.test_client()


@pytest.fixture
def make_session():
    """Build a Session directly, bypassing the socket layer."""

    def _make(room="test-room", gm_key=GM_KEY, name="Test Game"):
        session = Session(room, gm_key, name)
        mudfinder.ROOMS[room] = session
        return session

    return _make


@pytest.fixture
def client():
    """A connected Socket.IO test client."""
    test_client = mudfinder.socketio.test_client(mudfinder.app)
    yield test_client
    if test_client.is_connected():
        test_client.disconnect()


@pytest.fixture
def gm(client):
    """A test client that has created a room and joined it as GM.

    Returns (client, room, gmKey).
    """
    client.emit("create", {"name": "Test Game", "gmKey": GM_KEY})
    room = _first_event(client.get_received(), "create_room")["args"][0]["room"]
    client.emit("join_gm", {"room": room, "gmKey": GM_KEY})
    client.get_received()  # drain the gm_map / gm_update burst
    return client, room, GM_KEY


def _first_event(received, name):
    for packet in received:
        if packet["name"] == name:
            return packet
    raise AssertionError(
        "no %r event in received: %r" % (name, [p["name"] for p in received])
    )


def event(received, name):
    """Public helper: first packet named `name`, or AssertionError."""
    return _first_event(received, name)


def event_names(received):
    return [packet["name"] for packet in received]


def make_unit(**overrides):
    """A Unit with the minimum required key plus whatever the test needs."""
    data = {"charName": "Goblin"}
    data.update(overrides)
    return Unit(data)


def make_player(**overrides):
    data = {"charName": "Aria"}
    data.update(overrides)
    return Player(data)
