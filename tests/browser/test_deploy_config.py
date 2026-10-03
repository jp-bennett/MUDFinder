"""Run the production server the way deploy/ runs it, and open a websocket.

Everything else in tests/browser/ drives the Werkzeug development server that
`mudfinder.py` starts, because that is the convenient thing to launch from a
fixture. For a long time that meant the configuration in deploy/ -- the one
that serves actual games -- had never been started by any test at all, and it
was broken: it ran gevent-websocket's GeventWebSocketWorker, which handshakes
the websocket before Engine.IO does, so the browser saw two overlapping
upgrades and reported "Invalid frame header". Every page rendered perfectly.
No game ever loaded. The development server was fine throughout, so the whole
suite was green.

The `deployed_server` fixture reads its command line out of
deploy/systemd/mudfinder@.service rather than restating it, so editing that
unit back to a worker that cannot carry a websocket fails these tests. A
correct unit beside a stale copy here would have caught nothing.
"""

import pytest

pytestmark = pytest.mark.browser


def test_the_deployed_server_opens_a_websocket(deployed_server, new_client):
    """The failure this exists for: pages fine, websocket dead.

    Asserting on the transport and not just on socket.connected, because
    Socket.IO falls back to HTTP long-polling when the websocket upgrade
    fails. A configuration that polls forever is a working game that gets
    slower with every token moved, and it would pass a connectedness check.
    """
    client = new_client(deployed_server + "/")
    client.page.wait_for_function(
        "() => typeof socket !== 'undefined' && socket !== null && socket.connected",
        timeout=20000,
    )

    transport = client.page.evaluate("() => socket.io.engine.transport.name")
    assert transport == "websocket", (
        "connected over %r, not a websocket -- the upgrade failed and Socket.IO "
        "fell back to polling. Console: %r" % (transport, client.errors)
    )
    assert client.errors == []


def test_a_game_can_be_created_on_the_deployed_server(deployed_server, new_client):
    """Past the handshake and through one real exchange over the socket."""
    client = new_client(deployed_server + "/")
    client.page.wait_for_function(
        "() => typeof socket !== 'undefined' && socket !== null && socket.connected",
        timeout=20000,
    )
    client.page.fill("#gameName", "Deployed Config Game")
    client.page.click("text=Create Game")
    client.page.wait_for_url("**/gm.html*", timeout=20000)
    client.page.wait_for_selector("#mapForm", state="attached")
    assert client.page.evaluate("() => socket.io.engine.transport.name") == "websocket"
