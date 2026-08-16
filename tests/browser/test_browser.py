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

    def tile_count(self, client):
        """Count map tiles specifically.

        #mapGraphic also holds the background div, and in the GM view the
        undiscovered-tile washes, so its child count is not a tile count. The
        selector is scoped to the map because the tile-type palette in the
        toolbar reuses the mapTile class.
        """
        return client.page.eval_on_selector_all("#mapGraphic .mapTile", "els => els.length")

    def test_generated_map_renders_for_the_gm(self, gm_client):
        gm, _, _ = gm_client
        self.generate_map(gm, 5, 4)
        assert self.tile_count(gm) == 20

    def test_generated_map_reaches_a_joined_player(self, live_server, new_client, gm_client):
        gm, room, _ = gm_client
        player = new_client("%s/player.html?room=%s&charName=Aria" % (live_server, room))
        wait_for_socket(player)

        self.generate_map(gm, 5, 4)

        player.page.wait_for_function(
            "() => document.querySelectorAll('#mapGraphic .mapTile').length > 0",
            timeout=HANDSHAKE_TIMEOUT,
        )
        assert self.tile_count(player) == self.tile_count(gm)


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




# Every one of these paints through the background property -- the CSS classes
# for these types, and inline gradients for thin walls -- which the overlay
# used to overwrite.
TILE_KINDS = ["floorTile", "floorTileD", "wallTile", "doorClosed", "doorOpen", "stairsUp"]
WALL_CASES = [["left"], ["right"], ["top"], ["bottom"], ["left", "right", "top", "bottom"]]

# "Show Features" only bites when a map image has been uploaded: that is when
# tiles get the fullyTransparent class whose opacity the toggle drives.
DEFAULT_BACKGROUND = "static/images/mapbackground.jpg"
UPLOADED_BACKGROUND = "get_image.html?room=x&id=y"

# Measures every case in one pass. A fixture per case meant a fresh game per
# case, which was slow enough to exhaust the server's connections partway
# through. Each tile sits in the middle of a 3x3 grid because the door and
# stair branches look at their neighbours.
MEASURE_JS = """
([kinds, wallCases, defaultBg, uploadedBg]) => {
  showSeenOverlay = true;
  zoomSize = 70;
  const graphic = document.getElementById("mapGraphic");

  const build = (kind, seen, walls, background) => {
    const rows = [];
    for (let y = 0; y < 3; y++) {
      const row = [];
      for (let x = 0; x < 3; x++) {
        const middle = (x === 1 && y === 1);
        const cell = {tile: middle ? kind : "floorTile", walkable: true,
                      seen: seen, secret: false, x: x, y: y};
        if (middle && walls) { cell.walls = walls; }
        row.push(cell);
      }
      rows.push(row);
    }
    return {mapArray: rows, showBackground: true, mapBackground: background};
  };

  const measure = (kind, seen, walls, background) => {
    graphic.innerHTML = "";
    const tile = drawSingleTile(build(kind, seen, walls, background), 1, 1);
    graphic.appendChild(tile);
    const computed = getComputedStyle(tile);
    const wash = document.getElementById("wash1,1");
    const result = {
      opacity: computed.opacity,
      backgroundColor: computed.backgroundColor,
      backgroundImage: computed.backgroundImage,
      gradients: (computed.backgroundImage.match(/gradient/g) || []).length,
      washed: !!wash,
      washClickable: wash ? getComputedStyle(wash).pointerEvents !== "none" : null,
    };
    graphic.innerHTML = "";
    return result;
  };

  const out = {kinds: {}, walls: {}, features: {}};
  for (const kind of kinds) {
    out.kinds[kind] = {seen: measure(kind, true, null, defaultBg),
                       unseen: measure(kind, false, null, defaultBg)};
  }
  for (const walls of wallCases) {
    out.walls[walls.join("+")] = measure("floorTile", false, walls, defaultBg);
  }
  // The Show Features toggle drives the fullyTransparent rule's opacity.
  for (const featuresOn of [false, true]) {
    css_getclass(".fullyTransparent").style.opacity = featuresOn ? "" : "0";
    out.features[featuresOn ? "on" : "off"] = {
      seen: measure("wallTile", true, null, uploadedBg),
      unseen: measure("wallTile", false, null, uploadedBg),
    };
  }
  css_getclass(".fullyTransparent").style.opacity = "0";
  return out;
}
"""


@pytest.fixture(scope="module")
def overlay(browser, live_server):
    """Measure every overlay case once, in a single GM page."""
    context = browser.new_context(viewport={"width": 1000, "height": 700})
    try:
        page = context.new_page()
        page.goto(live_server + "/")
        page.wait_for_function(
            "() => typeof socket !== 'undefined' && socket !== null && socket.connected",
            timeout=HANDSHAKE_TIMEOUT,
        )
        page.fill("#gameName", "overlay measurements")
        page.click("text=Create Game")
        page.wait_for_url("**/gm.html*", timeout=HANDSHAKE_TIMEOUT)
        page.wait_for_selector("#mapForm", state="attached")
        return page.evaluate(
            MEASURE_JS, [TILE_KINDS, WALL_CASES, DEFAULT_BACKGROUND, UPLOADED_BACKGROUND]
        )
    finally:
        context.close()


class TestSeenOverlay:
    """The GM's "Show discovered overlay" marks tiles nobody has explored.

    It used to do that by writing white into the tile's style.background and
    forcing the tile visible. Both were wrong. Every tile type paints through
    background, so the wash replaced whatever the tile was drawing; and forcing
    the tile visible overrode "Show Features", which hides the feature layer
    through that same opacity. The wash is now its own element over the tile,
    so the tile is left entirely alone.
    """

    @pytest.mark.parametrize("kind", TILE_KINDS)
    def test_the_overlay_does_not_change_how_a_tile_is_painted(self, overlay, kind):
        """The invariant: the overlay adds a wash and changes nothing else."""
        seen, unseen = overlay["kinds"][kind]["seen"], overlay["kinds"][kind]["unseen"]
        assert unseen["backgroundColor"] == seen["backgroundColor"]
        assert unseen["backgroundImage"] == seen["backgroundImage"]
        assert unseen["opacity"] == seen["opacity"]

    @pytest.mark.parametrize("kind", TILE_KINDS)
    def test_every_tile_type_is_washed_when_undiscovered(self, overlay, kind):
        assert overlay["kinds"][kind]["unseen"]["washed"]

    @pytest.mark.parametrize("kind", TILE_KINDS)
    def test_no_tile_type_is_washed_once_discovered(self, overlay, kind):
        assert not overlay["kinds"][kind]["seen"]["washed"]

    def test_a_full_wall_tile_keeps_its_colour(self, overlay):
        """wallTile is the clearest case: a solid black tile turned white."""
        assert overlay["kinds"]["wallTile"]["unseen"]["backgroundColor"] == "rgb(0, 0, 0)"

    @pytest.mark.parametrize("kind,expected", [
        ("floorTileD", 2),
        ("doorClosed", 1),
        ("doorOpen", 1),
        ("stairsUp", 1),
    ])
    def test_tile_artwork_survives_the_overlay(self, overlay, kind, expected):
        assert overlay["kinds"][kind]["unseen"]["gradients"] == expected

    @pytest.mark.parametrize("walls,expected", [
        ("left", 1), ("right", 1), ("top", 1), ("bottom", 1),
        ("left+right+top+bottom", 4),
    ])
    def test_thin_walls_survive_the_overlay(self, overlay, walls, expected):
        assert overlay["walls"][walls]["gradients"] == expected
        assert overlay["walls"][walls]["washed"]

    def test_the_wash_does_not_swallow_clicks(self, overlay):
        """The GM still has to be able to paint on an undiscovered tile."""
        assert overlay["kinds"]["floorTile"]["unseen"]["washClickable"] is False


class TestSeenOverlayAgainstShowFeatures:
    """The two GM toggles are independent and must stay that way.

    "Show Features" hides the drawn feature layer over an uploaded map image by
    zeroing the tile's opacity. The overlay used to force that opacity back up
    so its wash would show, which dragged the features back into view with it.
    """

    def test_features_stay_hidden_on_undiscovered_tiles(self, overlay):
        assert overlay["features"]["off"]["unseen"]["opacity"] == "0"

    def test_undiscovered_tiles_are_still_marked_while_features_are_hidden(self, overlay):
        assert overlay["features"]["off"]["unseen"]["washed"]

    def test_features_show_on_undiscovered_tiles_when_asked_for(self, overlay):
        assert overlay["features"]["on"]["unseen"]["opacity"] == "1"

    @pytest.mark.parametrize("features", ["off", "on"])
    def test_the_overlay_never_alters_tile_opacity(self, overlay, features):
        """Whatever Show Features decided, discovered and undiscovered agree."""
        state = overlay["features"][features]
        assert state["unseen"]["opacity"] == state["seen"]["opacity"]
