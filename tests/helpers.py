"""Test helpers shared by the non-browser tests.

These deliberately live outside conftest.py: pytest imports every conftest as a
top-level module named "conftest", so once there is more than one of them (as
soon as tests/browser/ exists) "from conftest import ..." resolves to whichever
was imported first.
"""

from player import Player
from unit import Unit

GM_KEY = "test-gm-key"


def event(received, name):
    """The first packet named `name` from a test client's received list."""
    for packet in received:
        if packet["name"] == name:
            return packet
    raise AssertionError(
        "no %r event in received: %r" % (name, [p["name"] for p in received])
    )


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
