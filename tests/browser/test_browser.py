"""End-to-end tests driving a real browser against a real server.

The unit-level Socket.IO tests call the handlers directly, so they pass even
when no browser can reach the server. These tests are the ones that fail when
the vendored socket.io.js and the server-side libraries disagree about the
Engine.IO protocol -- the symptom is a 400 on the websocket handshake while
every page still renders normally.

Run just these:      pytest -m browser
Run everything else: pytest -m "not browser"
"""

import pytest

pytest.importorskip("playwright.sync_api")

pytestmark = pytest.mark.browser

HANDSHAKE_TIMEOUT = 15000


def wait_for_socket(client):
    client.page.wait_for_function(
        "() => typeof socket !== 'undefined' && socket !== null && socket.connected === true",
        timeout=HANDSHAKE_TIMEOUT,
    )


class TestHandshake:
    """The regression guard. Everything else depends on these passing."""

    def test_index_page_opens_a_websocket(self, live_server, new_client):
        client = new_client(live_server + "/")
        wait_for_socket(client)
        assert client.socket_connected()

    def test_index_page_reports_no_handshake_failure(self, live_server, new_client):
        client = new_client(live_server + "/")
        wait_for_socket(client)
        assert not [error for error in client.errors if "WebSocket" in error]

    def test_gm_page_opens_a_websocket(self, gm_client):
        client, _, _ = gm_client
        assert client.socket_connected()

    def test_player_page_opens_a_websocket(self, live_server, new_client, gm_client):
        _, room, _ = gm_client
        client = new_client("%s/player.html?room=%s&charName=Aria" % (live_server, room))
        wait_for_socket(client)
        assert client.socket_connected()

    def test_spectator_page_opens_a_websocket(self, live_server, new_client, gm_client):
        _, room, _ = gm_client
        client = new_client("%s/spectator.html?room=%s" % (live_server, room))
        wait_for_socket(client)
        assert client.socket_connected()


class TestGameCreation:
    def test_creating_a_game_lands_on_the_gm_view(self, gm_client):
        client, room, gm_key = gm_client
        assert "gm.html" in client.page.url
        assert room and gm_key

    def test_gm_view_offers_map_creation(self, gm_client):
        client, _, _ = gm_client
        assert client.page.is_visible("#mapForm")

    def test_gm_view_reports_no_javascript_errors(self, gm_client):
        client, _, _ = gm_client
        assert client.errors == []


class TestPlayerJoin:
    def test_player_sees_itself_in_its_own_unit_list(self, live_server, new_client, gm_client):
        _, room, _ = gm_client
        player = new_client("%s/player.html?room=%s&charName=Aria" % (live_server, room))
        player.page.wait_for_function(
            "() => document.getElementById('unitsDiv').innerText.includes('Aria')",
            timeout=HANDSHAKE_TIMEOUT,
        )
        assert "Aria" in player.page.inner_text("#unitsDiv")

    def test_player_appears_in_the_gm_player_list(self, live_server, new_client, gm_client):
        """The GM is told about the join itself, with no other event needed."""
        gm, room, _ = gm_client
        new_client("%s/player.html?room=%s&charName=Aria" % (live_server, room))
        gm.page.wait_for_function(
            "() => document.getElementById('connectedPlayers').innerText.includes('Aria')",
            timeout=HANDSHAKE_TIMEOUT,
        )
        assert "Aria" in gm.page.inner_text("#connectedPlayers")

    def test_player_appears_in_the_gm_unit_list(self, live_server, new_client, gm_client):
        gm, room, _ = gm_client
        new_client("%s/player.html?room=%s&charName=Aria" % (live_server, room))
        gm.page.wait_for_function(
            "() => document.getElementById('unitsDiv').innerText.includes('Aria')",
            timeout=HANDSHAKE_TIMEOUT,
        )
        assert "Aria" in gm.page.inner_text("#unitsDiv")

    def test_player_view_raises_no_javascript_exceptions(self, live_server, new_client, gm_client):
        _, room, _ = gm_client
        player = new_client("%s/player.html?room=%s&charName=Aria" % (live_server, room))
        wait_for_socket(player)
        player.page.wait_for_timeout(1000)
        assert player.page_errors == []


class TestMapSync:
    def generate_map(self, gm, width, height):
        gm.page.fill("#mapWidth", str(width))
        gm.page.fill("#mapHeight", str(height))
        gm.page.click("text=Generate Map")
        gm.page.wait_for_function(
            "() => document.getElementById('mapGraphic').children.length > 0",
            timeout=HANDSHAKE_TIMEOUT,
        )

    def test_generated_map_renders_for_the_gm(self, gm_client):
        gm, _, _ = gm_client
        self.generate_map(gm, 5, 4)
        tiles = gm.page.eval_on_selector("#mapGraphic", "el => el.children.length")
        assert tiles >= 20

    def test_generated_map_reaches_a_joined_player(self, live_server, new_client, gm_client):
        gm, room, _ = gm_client
        player = new_client("%s/player.html?room=%s&charName=Aria" % (live_server, room))
        wait_for_socket(player)

        self.generate_map(gm, 5, 4)

        player.page.wait_for_function(
            "() => document.getElementById('mapGraphic').children.length > 0",
            timeout=HANDSHAKE_TIMEOUT,
        )
        gm_tiles = gm.page.eval_on_selector("#mapGraphic", "el => el.children.length")
        player_tiles = player.page.eval_on_selector("#mapGraphic", "el => el.children.length")
        assert player_tiles == gm_tiles


class TestChat:
    def send_chat(self, client, message):
        client.page.fill("#newChat", message)
        client.page.press("#newChat", "Enter")

    def test_player_message_reaches_the_gm(self, live_server, new_client, gm_client):
        gm, room, _ = gm_client
        player = new_client("%s/player.html?room=%s&charName=Aria" % (live_server, room))
        wait_for_socket(player)

        self.send_chat(player, "hello from Aria")

        gm.page.wait_for_function(
            "() => document.getElementById('chatText').innerText.includes('hello from Aria')",
            timeout=HANDSHAKE_TIMEOUT,
        )
        assert "Aria" in gm.page.inner_text("#chatText")

    def test_gm_message_reaches_the_player(self, live_server, new_client, gm_client):
        gm, room, _ = gm_client
        player = new_client("%s/player.html?room=%s&charName=Aria" % (live_server, room))
        wait_for_socket(player)

        self.send_chat(gm, "the door creaks open")

        player.page.wait_for_function(
            "() => document.getElementById('chatText').innerText.includes('the door creaks open')",
            timeout=HANDSHAKE_TIMEOUT,
        )

    def test_roll_command_produces_a_result(self, live_server, new_client, gm_client):
        gm, room, _ = gm_client
        player = new_client("%s/player.html?room=%s&charName=Aria" % (live_server, room))
        wait_for_socket(player)

        self.send_chat(player, "/roll 1d1")

        # The command is echoed, then the evaluated total arrives as its own line.
        player.page.wait_for_function(
            "() => /Aria: 1\\s*$/m.test(document.getElementById('chatText').innerText)",
            timeout=HANDSHAKE_TIMEOUT,
        )

    def test_roll_result_is_shared_with_the_gm(self, live_server, new_client, gm_client):
        gm, room, _ = gm_client
        player = new_client("%s/player.html?room=%s&charName=Aria" % (live_server, room))
        wait_for_socket(player)

        self.send_chat(player, "/roll 1d1")

        gm.page.wait_for_function(
            "() => /Aria: 1\\s*$/m.test(document.getElementById('chatText').innerText)",
            timeout=HANDSHAKE_TIMEOUT,
        )


class TestStaticAssets:
    def test_no_local_asset_fails_to_load(self, live_server, new_client, gm_client):
        """A 404 on a script or stylesheet would break the views subtly."""
        _, room, _ = gm_client
        client = new_client("%s/player.html?room=%s&charName=Aria" % (live_server, room))
        wait_for_socket(client)
        client.page.wait_for_timeout(500)
        assert client.local_request_failures(live_server) == []


class TestSelfContained:
    """Every view must load entirely from this server.

    player.html used to pull a stylesheet from fontlibrary.org on every load,
    which made the page depend on a third party and fail when offline.
    """

    @pytest.mark.parametrize("page", ["player.html", "gm.html", "spectator.html"])
    def test_view_makes_no_third_party_requests(
        self, live_server, new_client, gm_client, page
    ):
        _, room, gm_key = gm_client
        client = new_client()
        external = []
        client.page.on(
            "request",
            lambda request: (
                external.append(request.url)
                if not request.url.startswith(live_server)
                else None
            ),
        )
        client.page.goto(
            "%s/%s?room=%s&charName=Aria&gmKey=%s" % (live_server, page, room, gm_key)
        )
        wait_for_socket(client)
        client.page.wait_for_timeout(500)
        assert external == []


# Renders one tile through the page's own drawSingleTile and reports what the
# browser actually computed for it. Driving the function directly keeps the
# test off the wall-painting toolbar, which is a lot of UI for one CSS rule.
DRAW_TILE_JS = """
([seen, walls]) => {
  showSeenOverlay = true;
  zoomSize = 70;
  const mapData = {
    mapArray: [[{tile: "floorTile", walkable: true, seen: seen, secret: false,
                 x: 0, y: 0, walls: walls}]],
    showBackground: true,
    mapBackground: "static/images/mapbackground.jpg",
  };
  const tile = drawSingleTile(mapData, 0, 0);
  document.body.appendChild(tile);
  const computed = getComputedStyle(tile);
  const result = {
    backgroundColor: computed.backgroundColor,
    gradients: (computed.backgroundImage.match(/linear-gradient/g) || []).length,
  };
  tile.remove();
  return result;
}
"""


class TestSeenOverlay:
    """The GM's "Show discovered overlay" whitens tiles nobody has explored.

    It used to do that by assigning style.background, which threw away the wall
    gradients composed onto the same property just above, so walls were
    invisible on exactly the part of the map the GM is working from.
    """

    def draw(self, gm, seen, walls):
        client, _, _ = gm
        return client.page.evaluate(DRAW_TILE_JS, [seen, walls])

    def test_walls_are_drawn_on_an_undiscovered_tile(self, gm_client):
        assert self.draw(gm_client, False, ["left", "top"])["gradients"] == 2

    def test_the_overlay_still_whitens_that_tile(self, gm_client):
        """Guards the fix from going too far the other way."""
        assert self.draw(gm_client, False, ["left", "top"])["backgroundColor"] == "rgb(255, 255, 255)"

    def test_an_undiscovered_tile_without_walls_is_plain_white(self, gm_client):
        result = self.draw(gm_client, False, None)
        assert result["backgroundColor"] == "rgb(255, 255, 255)"
        assert result["gradients"] == 0

    def test_a_discovered_tile_keeps_its_walls_and_is_not_whitened(self, gm_client):
        result = self.draw(gm_client, True, ["left", "top"])
        assert result["gradients"] == 2
        assert result["backgroundColor"] == "rgba(0, 0, 0, 0)"

    @pytest.mark.parametrize("walls,expected", [
        (["left"], 1),
        (["right"], 1),
        (["top"], 1),
        (["bottom"], 1),
        (["left", "right", "top", "bottom"], 4),
    ])
    def test_every_wall_side_survives_the_overlay(self, gm_client, walls, expected):
        assert self.draw(gm_client, False, walls)["gradients"] == expected
