"""End-to-end tests driving a real browser against a real server.

The unit-level Socket.IO tests call the handlers directly, so they pass even
when no browser can reach the server. These tests are the ones that fail when
the vendored socket.io.js and the server-side libraries disagree about the
Engine.IO protocol -- the symptom is a 400 on the websocket handshake while
every page still renders normally.

Run just these:      pytest -m browser
Run everything else: pytest -m "not browser"
"""

from urllib.parse import quote

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


class TestThePlayerLinksPanel:
    """The GM's panel of per-player links, and the Delete button beside each.

    A player names itself, and the server stores that name as it is given, so
    the name arrives here as untrusted text. The panel is built as elements
    for that reason; assembled as markup, a name carrying a quote or a tag
    escaped its row and ran as script.
    """

    HOSTILE_NAME = "Ari'a<img src=x onerror=\"window.pwned=1\">"

    def test_a_player_gets_a_row_with_a_link_and_a_delete_button(
        self, live_server, new_client, gm_client
    ):
        gm, room, _ = gm_client
        new_client("%s/player.html?room=%s&charName=Aria" % (live_server, room))
        gm.page.wait_for_function(
            "() => document.querySelector('#links .linkRow') !== null",
            timeout=HANDSHAKE_TIMEOUT,
        )
        row = gm.page.query_selector("#links .linkRow")
        assert row.query_selector("a").inner_text() == "Aria"
        assert row.query_selector("button").inner_text() == "Delete"

    def test_the_link_carries_the_room_and_the_name(self, live_server, new_client, gm_client):
        gm, room, _ = gm_client
        new_client("%s/player.html?room=%s&charName=Aria" % (live_server, room))
        gm.page.wait_for_function(
            "() => document.querySelector('#links .linkRow a') !== null",
            timeout=HANDSHAKE_TIMEOUT,
        )
        href = gm.page.get_attribute("#links .linkRow a", "href")
        assert "room=%s" % room in href
        assert "charName=Aria" in href

    def test_a_name_full_of_markup_stays_text(self, live_server, new_client, gm_client):
        """The name lands in the row as a word, not as the tag it spells.

        Scoped to the panel on purpose. Other lists on this page still build
        their rows out of markup and do run the tag -- #unitsDiv is one -- so
        an assertion about the whole document would be reporting those, not
        this.
        """
        gm, room, _ = gm_client
        new_client(
            "%s/player.html?room=%s&charName=%s"
            % (live_server, room, quote(self.HOSTILE_NAME, safe=""))
        )
        gm.page.wait_for_function(
            """(name) => Array.from(document.querySelectorAll("#links .linkRow a"))
                 .some(a => a.innerText === name)""",
            arg=self.HOSTILE_NAME,
            timeout=HANDSHAKE_TIMEOUT,
        )
        assert gm.page.query_selector("#links img") is None
        assert gm.page.eval_on_selector(
            "#links", "el => el.querySelectorAll('*').length"
        ) == gm.page.eval_on_selector(
            "#links",
            # heading + one row per player, each holding an anchor and a button
            "el => 1 + el.querySelectorAll('.linkRow').length * 3",
        )

    def test_the_panel_builds_without_raising(self, live_server, new_client, gm_client):
        gm, room, _ = gm_client
        new_client(
            "%s/player.html?room=%s&charName=%s"
            % (live_server, room, quote(self.HOSTILE_NAME, safe=""))
        )
        gm.page.wait_for_timeout(1000)
        assert gm.page_errors == []


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


DISCOVER_JS = """
() => {
  showSeenOverlay = true;
  zoomSize = 70;
  const build = (seen) => {
    const rows = [];
    for (let y = 0; y < 3; y++) {
      const row = [];
      for (let x = 0; x < 3; x++) {
        row.push({tile: "floorTile", walkable: true, secret: false, x: x, y: y,
                  seen: (x === 1 && y === 1) ? seen : true});
      }
      rows.push(row);
    }
    return {mapArray: rows, showBackground: true,
            mapBackground: "static/images/mapbackground.jpg"};
  };
  const mapData = build(false);
  drawMap(mapData);
  const before = !!document.getElementById("wash1,1");
  // Exactly what the gm_map_update handler does when a tile is discovered.
  updateMap({mapArray: [{tile: "floorTile", walkable: true, seen: true,
                         secret: false, x: 1, y: 1}],
             mapBackground: mapData.mapBackground}, mapData);
  return {before: before,
          after: !!document.getElementById("wash1,1"),
          remaining: document.querySelectorAll(".undiscoveredTile").length};
}
"""


@pytest.fixture(scope="module")
def discovery(browser, live_server):
    """Discover a tile in place, the way gm_map_update does."""
    context = browser.new_context(viewport={"width": 1000, "height": 700})
    try:
        page = context.new_page()
        page.goto(live_server + "/")
        page.wait_for_function(
            "() => typeof socket !== 'undefined' && socket !== null && socket.connected",
            timeout=HANDSHAKE_TIMEOUT,
        )
        page.fill("#gameName", "discovery")
        page.click("text=Create Game")
        page.wait_for_url("**/gm.html*", timeout=HANDSHAKE_TIMEOUT)
        page.wait_for_selector("#mapForm", state="attached")
        return page.evaluate(DISCOVER_JS)
    finally:
        context.close()


class TestDiscoveringATile:
    """A tile becoming discovered has to stop being marked straight away.

    updateMap redraws a single tile in place rather than rebuilding the map, so
    the wash has to be cleared on every redraw, not only when a new one is
    drawn. Otherwise the mark lingers until something forces a full redraw --
    toggling the overlay off and on, for instance.
    """

    def test_an_undiscovered_tile_starts_marked(self, discovery):
        assert discovery["before"]

    def test_the_mark_goes_when_the_tile_is_discovered(self, discovery):
        assert not discovery["after"]

    def test_no_wash_is_left_behind_anywhere(self, discovery):
        assert discovery["remaining"] == 0


# Draws a 3x3 map over the given background with the top row discovered and
# the rest not, then reports what the toggles did to it.
FEATURES_JS = """
([background]) => {
  showSeenOverlay = true;
  zoomSize = 70;
  const rows = [];
  for (let y = 0; y < 3; y++) {
    const row = [];
    for (let x = 0; x < 3; x++) {
      row.push({tile: "wallTile", walkable: true, secret: false, x: x, y: y,
                seen: (y === 0)});
    }
    rows.push(row);
  }
  mapObject = {mapArray: rows, showBackground: true, mapBackground: background};
  drawMap(mapObject);
  return {
    discoveredOpacity: getComputedStyle(document.getElementById("tile1,0")).opacity,
    undiscoveredOpacity: getComputedStyle(document.getElementById("tile1,1")).opacity,
    undiscoveredMarked: !!document.getElementById("wash1,1"),
    discoveredMarked: !!document.getElementById("wash1,0"),
  };
}
"""


@pytest.fixture(scope="module")
def features(browser, live_server):
    """Drive the real Show Features checkbox over both kinds of map."""
    context = browser.new_context(viewport={"width": 1100, "height": 700})
    try:
        page = context.new_page()
        page.goto(live_server + "/")
        page.wait_for_function(
            "() => typeof socket !== 'undefined' && socket !== null && socket.connected",
            timeout=HANDSHAKE_TIMEOUT,
        )
        page.fill("#gameName", "features")
        page.click("text=Create Game")
        page.wait_for_url("**/gm.html*", timeout=HANDSHAKE_TIMEOUT)
        page.wait_for_selector("#mapForm", state="attached")

        results = {"defaultChecked": page.is_checked("#showFeatures")}
        for label, background in (("generated", DEFAULT_BACKGROUND),
                                  ("uploaded", UPLOADED_BACKGROUND)):
            for shown in (True, False):
                page.set_checked("#showFeatures", shown)
                results["%s|%s" % (label, "on" if shown else "off")] = page.evaluate(
                    FEATURES_JS, [background]
                )
        return results
    finally:
        context.close()


class TestShowFeatures:
    """One checkbox governing the feature layer, on either kind of map.

    It only ever drove the fullyTransparent class, which a tile carries over an
    uploaded map image. Over the default background a tile carries
    slightlyTransparent instead, so on a generated map the checkbox changed a
    rule that matched nothing and features could not be turned off at all.
    """

    def test_features_are_shown_by_default(self, features):
        """Otherwise a generated map, whose features are the map, loads blank."""
        assert features["defaultChecked"]

    @pytest.mark.parametrize("background", ["generated", "uploaded"])
    def test_features_are_visible_when_the_box_is_checked(self, features, background):
        assert float(features["%s|on" % background]["discoveredOpacity"]) > 0

    @pytest.mark.parametrize("background", ["generated", "uploaded"])
    def test_features_are_hidden_when_the_box_is_cleared(self, features, background):
        assert features["%s|off" % background]["discoveredOpacity"] == "0"

    @pytest.mark.parametrize("background", ["generated", "uploaded"])
    def test_undiscovered_tiles_follow_the_same_setting(self, features, background):
        """The overlay must not be a way round the toggle."""
        state = features["%s|off" % background]
        assert state["undiscoveredOpacity"] == state["discoveredOpacity"] == "0"

    @pytest.mark.parametrize("background,shown", [
        ("generated", "on"), ("generated", "off"),
        ("uploaded", "on"), ("uploaded", "off"),
    ])
    def test_undiscovered_tiles_stay_marked_either_way(self, features, background, shown):
        """Hiding features must not also hide which ground is unexplored."""
        assert features["%s|%s" % (background, shown)]["undiscoveredMarked"]

    @pytest.mark.parametrize("background,shown", [
        ("generated", "on"), ("generated", "off"),
        ("uploaded", "on"), ("uploaded", "off"),
    ])
    def test_discovered_tiles_are_never_marked(self, features, background, shown):
        assert not features["%s|%s" % (background, shown)]["discoveredMarked"]


BACKGROUND_REPORT_JS = """
() => {
  const tile = document.getElementById("tile1,1");
  const backgroundDiv = document.getElementById("mapBackgroundDiv");
  return {
    featuresChecked: document.getElementById("showFeatures").checked,
    tileOpacity: tile ? getComputedStyle(tile).opacity : null,
    backgroundImage: backgroundDiv ? backgroundDiv.style.backgroundImage : null,
    mapObjectBackground: (typeof mapObject !== "undefined" && mapObject)
      ? String(mapObject.mapBackground) : null,
  };
}
"""

UPLOADED_MAP_URL = "https://example.invalid/battlemap.png"


@pytest.fixture(scope="module")
def background_walkthrough(browser, live_server):
    """Generate a map, set a background on it, then redraw.

    Goes through the same image_upload event the Background button sends, so
    the server side of setting a background is covered too.
    """
    context = browser.new_context(viewport={"width": 1100, "height": 700})
    try:
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(live_server + "/")
        page.wait_for_function(
            "() => typeof socket !== 'undefined' && socket !== null && socket.connected",
            timeout=HANDSHAKE_TIMEOUT,
        )
        page.fill("#gameName", "background walkthrough")
        page.click("text=Create Game")
        page.wait_for_url("**/gm.html*", timeout=HANDSHAKE_TIMEOUT)

        page.fill("#mapWidth", "4")
        page.fill("#mapHeight", "3")
        page.click("text=Generate Map")
        page.wait_for_function(
            "() => document.querySelectorAll('#mapGraphic .mapTile').length > 0",
            timeout=HANDSHAKE_TIMEOUT,
        )
        stages = {"generated": page.evaluate(BACKGROUND_REPORT_JS)}

        page.evaluate(
            """(url) => socket.emit("image_upload", room, url, "mapBackground", "")""",
            UPLOADED_MAP_URL,
        )
        page.wait_for_function(
            """(url) => document.getElementById("mapBackgroundDiv")
                 .style.backgroundImage.includes(url)""",
            arg=UPLOADED_MAP_URL,
            timeout=HANDSHAKE_TIMEOUT,
        )
        stages["backgroundSet"] = page.evaluate(BACKGROUND_REPORT_JS)

        # A full redraw, as a reload or any map edit would cause. This is where
        # the tiles pick up fullyTransparent and used to cover the image.
        page.evaluate("() => drawMap(mapObject)")
        stages["redrawn"] = page.evaluate(BACKGROUND_REPORT_JS)

        page.set_checked("#showFeatures", True)
        page.evaluate("() => drawMap(mapObject)")
        stages["featuresRequested"] = page.evaluate(BACKGROUND_REPORT_JS)

        stages["errors"] = errors
        return stages
    finally:
        context.close()


class TestSettingABackground:
    """Uploading a map image has to leave the image visible.

    Tiles carry fullyTransparent over an uploaded background, so once the
    Show Features checkbox drove that class on generated maps as well, its
    default of checked meant an opaque grid was drawn over the artwork the GM
    had just chosen. The default now follows the kind of map.
    """

    def test_the_background_is_applied(self, background_walkthrough):
        assert UPLOADED_MAP_URL in background_walkthrough["backgroundSet"]["backgroundImage"]

    def test_features_switch_off_for_an_uploaded_map(self, background_walkthrough):
        assert not background_walkthrough["backgroundSet"]["featuresChecked"]

    def test_the_image_is_not_covered_after_a_redraw(self, background_walkthrough):
        """The redraw is when tiles pick up fullyTransparent."""
        assert background_walkthrough["redrawn"]["tileOpacity"] == "0"

    def test_the_background_survives_a_redraw(self, background_walkthrough):
        assert UPLOADED_MAP_URL in background_walkthrough["redrawn"]["backgroundImage"]

    def test_the_map_object_learns_the_new_background(self, background_walkthrough):
        """Otherwise a later redraw from it puts the old background back."""
        assert background_walkthrough["redrawn"]["mapObjectBackground"] == UPLOADED_MAP_URL

    def test_a_generated_map_still_shows_its_features(self, background_walkthrough):
        generated = background_walkthrough["generated"]
        assert generated["featuresChecked"]
        assert float(generated["tileOpacity"]) > 0

    def test_the_gm_can_still_turn_features_on_over_the_image(self, background_walkthrough):
        assert background_walkthrough["featuresRequested"]["tileOpacity"] == "1"

    def test_nothing_raised(self, background_walkthrough):
        assert background_walkthrough["errors"] == []


BATTLEMAP_IMAGE = "https://example.invalid/gunalley.png"

BACKGROUND_GEOMETRY_JS = """
() => {
  const div = document.getElementById("mapBackgroundDiv");
  const computed = div ? getComputedStyle(div) : null;
  const tile = document.getElementById("tile0,0");
  return {
    backgroundSize: computed ? computed.backgroundSize : null,
    backgroundPosition: computed ? computed.backgroundPosition : null,
    tilesWide: (typeof mapObject !== "undefined" && mapObject)
      ? mapObject.backgroundTilesWide : null,
    offsetX: (typeof mapObject !== "undefined" && mapObject)
      ? mapObject.backgroundOffsetX : null,
    offsetY: (typeof mapObject !== "undefined" && mapObject)
      ? mapObject.backgroundOffsetY : null,
    aligning: document.getElementById("mapGraphic").classList.contains("aligning"),
    tileOpacity: tile ? getComputedStyle(tile).opacity : null,
    tilePitch: tile ? tile.getBoundingClientRect().width : null,
    gridAcross: (typeof mapObject !== "undefined" && mapObject && mapObject.mapArray
                 && mapObject.mapArray[0]) ? mapObject.mapArray[0].length : 0,
    gridDown: (typeof mapObject !== "undefined" && mapObject && mapObject.mapArray)
                 ? mapObject.mapArray.length : 0,
    // Absent in the player view, which this probe also runs against.
    setupOpen: document.getElementById("alignmentControls")
      ? getComputedStyle(document.getElementById("alignmentControls")).display !== "none"
      : null,
  };
}
"""


@pytest.fixture(scope="module")
def battlemap(browser, live_server):
    """Build a battlemap from an image and align it, the way a GM would."""
    context = browser.new_context(viewport={"width": 1200, "height": 800})
    try:
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(live_server + "/")
        page.wait_for_function(
            "() => typeof socket !== 'undefined' && socket !== null && socket.connected",
            timeout=HANDSHAKE_TIMEOUT,
        )
        page.fill("#gameName", "battlemap")
        page.click("text=Create Game")
        page.wait_for_url("**/gm.html*", timeout=HANDSHAKE_TIMEOUT)
        page.wait_for_selector("#mapForm", state="attached")
        room = dict(pair.split("=", 1) for pair in page.url.split("?", 1)[1].split("&"))["room"]

        stages = {}

        # The Choose Image button goes through the existing upload modal, which
        # ends in this event. On an empty map that starts battlemap setup by
        # itself, with a grid guessed from the image's shape.
        page.evaluate(
            """(url) => socket.emit("image_upload", room, url, "mapBackground", "")""",
            BATTLEMAP_IMAGE,
        )
        page.wait_for_function(
            "() => document.querySelectorAll('#mapGraphic .mapTile').length > 0",
            timeout=HANDSHAKE_TIMEOUT,
        )
        stages["setupStarted"] = page.evaluate(BACKGROUND_GEOMETRY_JS)

        # Then the square count is set from within setup.
        page.fill("#alignGridWidth", "22")
        page.dispatch_event("#alignGridWidth", "change")
        page.fill("#alignGridHeight", "34")
        page.dispatch_event("#alignGridHeight", "change")
        page.wait_for_function(
            "() => mapObject.mapArray.length === 34 && mapObject.mapArray[0].length === 22",
            timeout=HANDSHAKE_TIMEOUT,
        )
        stages["created"] = page.evaluate(BACKGROUND_GEOMETRY_JS)

        page.fill("#alignTilesWide", "24.5")
        page.dispatch_event("#alignTilesWide", "change")
        # Waited on the value, not on a duration. A fixed pause here was long
        # enough on a developer machine and not on a CI runner, so the change
        # was measured one stage late and two assertions swapped their answers.
        page.wait_for_function(
            "() => mapObject.backgroundTilesWide === 24.5", timeout=HANDSHAKE_TIMEOUT)
        # And then on the paint. The number is set locally the moment the field
        # changes, but the artwork is only resized when the change comes back
        # from the server -- so waiting on the number alone reads the stage
        # before the one being asserted, and any change in how long the page
        # takes to load decides which of the two is measured.
        page.wait_for_function(
            """(was) => getComputedStyle(
                 document.getElementById("mapBackgroundDiv")).backgroundSize !== was""",
            arg=stages["created"]["backgroundSize"], timeout=HANDSHAKE_TIMEOUT)
        stages["scaled"] = page.evaluate(BACKGROUND_GEOMETRY_JS)

        # Drag two squares right and one down, at 70px per square.
        box = page.locator("#mapContainer").bounding_box()
        page.mouse.move(box["x"] + 300, box["y"] + 300)
        page.mouse.down()
        page.mouse.move(box["x"] + 440, box["y"] + 370, steps=8)
        page.mouse.up()
        page.wait_for_function(
            "() => mapObject.backgroundOffsetX === 2 && mapObject.backgroundOffsetY === 1",
            timeout=HANDSHAKE_TIMEOUT)
        stages["dragged"] = page.evaluate(BACKGROUND_GEOMETRY_JS)

        # A full redraw, as toggling the discovered overlay causes.
        page.evaluate("() => drawMap(mapObject)")
        stages["redrawn"] = page.evaluate(BACKGROUND_GEOMETRY_JS)

        # Zoom is a CSS transform over the whole map, so alignment must be
        # untouched by it.
        page.evaluate("""() => { zoom = 2;
            document.getElementById("mapGraphic").style.transform = "scale(2)"; }""")
        page.wait_for_timeout(200)
        stages["zoomed"] = page.evaluate(BACKGROUND_GEOMETRY_JS)
        page.evaluate("""() => { zoom = 1;
            document.getElementById("mapGraphic").style.transform = "scale(1)"; }""")

        # Grow the grid with a nudge button, and confirm the image does not
        # move when the square count does.
        before_resize = page.evaluate(BACKGROUND_GEOMETRY_JS)
        page.click("#alignmentControls button:has-text('+') >> nth=0")
        page.wait_for_function(
            "(n) => mapObject.mapArray[0].length === n", arg=23, timeout=HANDSHAKE_TIMEOUT)
        after = page.evaluate(BACKGROUND_GEOMETRY_JS)
        stages["nudgedGrid"] = {"before": before_resize, "after": after}

        # Three edits with no pause between them. Each one is echoed back by
        # the server, and a slow echo must not undo a newer local change.
        page.fill("#alignTilesWide", "12.4")
        page.dispatch_event("#alignTilesWide", "change")
        page.fill("#alignOffsetX", "-1.2")
        page.dispatch_event("#alignOffsetX", "change")
        page.fill("#alignOffsetY", "-0.6")
        page.dispatch_event("#alignOffsetY", "change")
        page.wait_for_function(
            "() => mapObject.backgroundOffsetY === -0.6", timeout=HANDSHAKE_TIMEOUT)
        stages["rapid"] = page.evaluate(BACKGROUND_GEOMETRY_JS)
        # Three changes went out and the newest is what is on screen, so every
        # echo has been judged against the stamp rather than applied blindly.
        stages["seqShown"] = page.evaluate("() => alignmentSeqShown")

        # A refresh while the GM is typing must leave that box alone. The
        # half-typed value is put back before blurring, because blurring a
        # changed field fires change, which would really move the image and
        # leak into the stages below.
        page.focus("#alignOffsetY")
        stages["typing"] = page.evaluate("""() => {
            const editing = document.getElementById("alignOffsetY");
            const other = document.getElementById("alignOffsetX");
            const original = editing.value;
            editing.value = "-9.9";          // part way through typing
            refreshAlignmentFields();
            const result = {editing: editing.value, other: other.value};
            editing.value = original;
            editing.blur();
            return result;
        }""")

        # The staleness rule on its own. Losing the race on purpose is not
        # reproducible, so the rule it enforces is checked directly. An update
        # stamped behind what is on screen is stripped; one stamped ahead of it
        # is applied and becomes the new mark.
        stages["echo"] = page.evaluate("""() => {
            const shown = alignmentSeqShown;
            const stale = {backgroundTilesWide: 99, backgroundOffsetX: 9,
                           backgroundOffsetY: 9, backgroundAlignmentSeq: shown - 1};
            const droppedStale = dropOwnAlignmentEcho(stale);
            const fresh = {backgroundTilesWide: 99, backgroundOffsetX: 9,
                           backgroundOffsetY: 9, backgroundAlignmentSeq: shown + 1};
            const droppedFresh = dropOwnAlignmentEcho(fresh);
            return {droppedStale: droppedStale,
                    staleStripped: !("backgroundTilesWide" in stale),
                    droppedFresh: droppedFresh,
                    freshKept: "backgroundTilesWide" in fresh,
                    markMoved: alignmentSeqShown === shown + 1};
        }""")

        # And the same rule where it actually bit: a whole map, sent in answer
        # to a grid resize, carrying an alignment older than what is on screen.
        stages["staleFullMap"] = page.evaluate("""() => {
            const before = {tilesWide: mapObject.backgroundTilesWide,
                            offsetX: mapObject.backgroundOffsetX};
            const resizeAnswer = {mapArray: mapObject.mapArray,
                                  backgroundTilesWide: 20,
                                  backgroundOffsetX: 0,
                                  backgroundOffsetY: 0,
                                  backgroundAlignmentSeq: alignmentSeqShown - 1};
            keepLocalAlignmentIfPending(resizeAnswer);
            return {before: before,
                    kept: {tilesWide: resizeAnswer.backgroundTilesWide,
                           offsetX: resizeAnswer.backgroundOffsetX}};
        }""")

        # What a player sees of the same room.
        player = context.new_page()
        player.goto("%s/player.html?room=%s&charName=Aria" % (live_server, room))
        player.wait_for_function(
            "() => document.querySelectorAll('#mapGraphic .mapTile').length > 0",
            timeout=HANDSHAKE_TIMEOUT,
        )
        stages["player"] = player.evaluate(BACKGROUND_GEOMETRY_JS)

        # Clearing back to a plain generated map must restore the old rendering.
        page.evaluate("""() => socket.emit("clear_map",
            {room: room, gmKey: gmKey, clearLocations: true})""")
        page.wait_for_timeout(500)
        page.fill("#mapWidth", "4")
        page.fill("#mapHeight", "3")
        page.click("text=Generate Map")
        page.wait_for_function(
            "() => document.querySelectorAll('#mapGraphic .mapTile').length > 0",
            timeout=HANDSHAKE_TIMEOUT,
        )
        stages["generated"] = page.evaluate(BACKGROUND_GEOMETRY_JS)

        stages["errors"] = errors
        return stages
    finally:
        context.close()


class TestBattlemapFromAnImage:
    """A GM uploads a battlemap, says how big it is, and lines it up.

    The image used to be stretched to fill the play area with background-size:
    cover and no background-position, so a map's printed squares could not be
    made to coincide with the play grid, and distances were wrong.
    """

    def test_setup_starts_from_the_image(self, battlemap):
        """Choosing an image on an empty map lays a grid and opens setup,
        without the GM having to guess a square count first."""
        started = battlemap["setupStarted"]
        assert started["gridAcross"] == 20
        assert started["setupOpen"]

    def test_the_square_count_can_be_changed_during_setup(self, battlemap):
        """The count is the hard thing to know before seeing the grid on the
        artwork, so it has to be adjustable from inside setup."""
        assert battlemap["created"]["gridAcross"] == 22
        assert battlemap["created"]["gridDown"] == 34

    def test_resizing_the_grid_leaves_the_image_where_it_was(self, battlemap):
        """Changing how many squares the map is says nothing about how big the
        artwork should be. 20 squares at 70px, as setup started it."""
        assert battlemap["created"]["backgroundSize"] == "1400px"

    def test_the_image_starts_on_the_grid_origin(self, battlemap):
        assert battlemap["setupStarted"]["backgroundPosition"] == "0px 0px"

    def test_it_drops_into_alignment_mode(self, battlemap):
        """A fresh grid almost never matches the image's printed one."""
        assert battlemap["setupStarted"]["aligning"]

    def test_the_grid_is_visible_to_align_against(self, battlemap):
        """Tiles over an uploaded image are transparent; alignment shows them."""
        assert battlemap["created"]["tileOpacity"] == "1"

    def test_the_scale_field_resizes_the_image(self, battlemap):
        """24.5 squares at 70px."""
        assert battlemap["scaled"]["backgroundSize"] == "1715px"
        assert battlemap["scaled"]["tilesWide"] == 24.5

    def test_dragging_moves_the_image_by_whole_squares(self, battlemap):
        """140px right and 70px down, at 70px per square."""
        assert battlemap["dragged"]["offsetX"] == pytest.approx(2, abs=0.01)
        assert battlemap["dragged"]["offsetY"] == pytest.approx(1, abs=0.01)

    def test_dragging_is_applied_to_the_image(self, battlemap):
        assert battlemap["dragged"]["backgroundPosition"] == "140px 70px"

    def test_alignment_survives_a_full_redraw(self, battlemap):
        redrawn, dragged = battlemap["redrawn"], battlemap["dragged"]
        assert redrawn["backgroundSize"] == dragged["backgroundSize"]
        assert redrawn["backgroundPosition"] == dragged["backgroundPosition"]

    def test_zoom_does_not_disturb_the_alignment(self, battlemap):
        """The invariant. Zoom scales the whole map, so the image and the grid
        have to move together or a zoomed-in GM sees a map that has drifted."""
        zoomed, before = battlemap["zoomed"], battlemap["redrawn"]
        assert zoomed["backgroundSize"] == before["backgroundSize"]
        assert zoomed["backgroundPosition"] == before["backgroundPosition"]

    def test_zoom_scaled_the_map_at_all(self, battlemap):
        """Guards the test above from passing because nothing happened."""
        assert battlemap["zoomed"]["tilePitch"] > battlemap["redrawn"]["tilePitch"] * 1.5

    def test_edits_in_quick_succession_all_stick(self, battlemap):
        """The outcome a GM cares about. Note this does not deliberately lose
        the echo race, which is not reproducible on demand; the rule that
        prevents it is checked in TestAlignmentEchoes."""
        rapid = battlemap["rapid"]
        assert rapid["tilesWide"] == pytest.approx(12.4)
        assert rapid["offsetX"] == pytest.approx(-1.2)
        assert rapid["offsetY"] == pytest.approx(-0.6)

    def test_players_get_the_same_alignment(self, battlemap):
        """Players move on this grid, so their artwork has to sit where the
        GM's does. Compared against the state the GM was in when the player
        loaded, which is after the rapid edits above."""
        assert battlemap["player"]["backgroundSize"] == battlemap["rapid"]["backgroundSize"]
        assert battlemap["player"]["backgroundPosition"] == battlemap["rapid"]["backgroundPosition"]

    def test_a_plain_generated_map_is_still_stretched_to_fit(self, battlemap):
        """The compatibility hinge: a map with no alignment renders as before."""
        assert battlemap["generated"]["backgroundSize"] == "cover"
        assert battlemap["generated"]["tilesWide"] is None

    def test_alignment_mode_lets_go_of_a_plain_map(self, battlemap):
        """There is nothing to align, and the mode strips tile art."""
        assert not battlemap["generated"]["aligning"]

    def test_nothing_raised(self, battlemap):
        assert battlemap["errors"] == []


class TestAlignmentEchoes:
    """Alignment changes come back from the server, and one that is behind
    what is already on screen must not undo a later adjustment.

    Which payload is older is decided by the stamp the server puts on every
    alignment write, not by whether this client has a send outstanding. The
    payload that used to win this race was not an echo of our own change at
    all -- it was a whole map answering an earlier grid resize.
    """

    def test_a_stale_update_is_dropped(self, battlemap):
        assert battlemap["echo"]["droppedStale"]

    def test_the_dropped_update_carries_no_alignment_on(self, battlemap):
        """Stripped rather than ignored, so updateMap cannot apply it either."""
        assert battlemap["echo"]["staleStripped"]

    def test_a_newer_change_is_kept(self, battlemap):
        """A second GM tab moving the image sends a higher stamp, and that has
        to be applied or the two views never agree."""
        assert not battlemap["echo"]["droppedFresh"]
        assert battlemap["echo"]["freshKept"]

    def test_accepting_one_moves_the_mark(self, battlemap):
        """Otherwise the same update would be accepted twice."""
        assert battlemap["echo"]["markMoved"]

    def test_the_guard_is_wired_into_the_handler(self, battlemap):
        """Three changes were sent and the last of them is what is on screen,
        so the echoes were judged rather than applied blindly."""
        assert battlemap["seqShown"] > 0


class TestAStaleFullMapCannotUndoADrag:
    """The failure this replaced a counter to fix.

    Resizing the grid answers with a whole map, carrying the alignment as it
    stood when the resize was handled. On a slow connection that map arrives
    after the GM has dragged the image, and the old guard had already stood
    down by then -- it counted our own sends, and this is not one.
    """

    def test_the_stale_map_does_not_move_the_image(self, battlemap):
        before = battlemap["staleFullMap"]["before"]
        kept = battlemap["staleFullMap"]["kept"]
        assert kept["tilesWide"] == before["tilesWide"]
        assert kept["offsetX"] == before["offsetX"]

    def test_it_was_carrying_something_different(self, battlemap):
        """Otherwise the test above would pass for the wrong reason."""
        assert battlemap["staleFullMap"]["before"]["tilesWide"] != 20


class TestTypingIntoAlignmentFields:
    """The alignment boxes are refreshed on every map update, and a GM part
    way through typing a value must not have it replaced under them."""

    def test_the_field_being_typed_into_is_left_alone(self, battlemap):
        assert battlemap["typing"]["editing"] == "-9.9"

    def test_the_other_fields_still_refresh(self, battlemap):
        """Only the focused box is protected, not the whole panel."""
        assert battlemap["typing"]["other"] == "-1.20"


def write_blob(path, size):
    """A file of a given size. Only its size matters to the upload guard, and
    generating megabytes of valid PNG per test run is not worth the seconds."""
    with open(path, "wb") as blob:
        blob.write(b"\0" * size)
    return str(path)


@pytest.fixture(scope="module")
def uploads(browser, live_server, tmp_path_factory):
    """Upload images through the real Choose Image modal, at two sizes.

    Over the socket a file becomes base64, a third larger again. The transport
    used to cap a message at a megabyte and drop the connection when one went
    over, so an ordinary battlemap killed the websocket and the page stopped
    responding without saying anything.
    """
    directory = tmp_path_factory.mktemp("uploads")
    ordinary = write_blob(directory / "battlemap.png", 3 * 1024 * 1024)
    enormous = write_blob(directory / "enormous.png", 20 * 1024 * 1024)

    context = browser.new_context(viewport={"width": 1200, "height": 800})
    try:
        results = {}
        for label, path in (("ordinary", ordinary), ("enormous", enormous)):
            page = context.new_page()
            alerts = []
            page.on("dialog", lambda dialog: (alerts.append(dialog.message), dialog.dismiss()))
            page.goto(live_server + "/")
            page.wait_for_function(
                "() => typeof socket !== 'undefined' && socket !== null && socket.connected",
                timeout=HANDSHAKE_TIMEOUT,
            )
            page.fill("#gameName", "upload " + label)
            page.click("text=Create Game")
            page.wait_for_url("**/gm.html*", timeout=HANDSHAKE_TIMEOUT)
            page.wait_for_selector("#mapForm", state="attached")

            page.click("text=Choose Image")
            page.wait_for_selector("#imageFileUpload")
            page.set_input_files("#imageFileUpload", path)
            page.click('#modalBackground button:has-text("Select")')
            page.wait_for_timeout(3000)

            results[label] = {
                "connected": page.evaluate("() => socket && socket.connected"),
                "background": page.evaluate(
                    """() => (typeof mapObject !== 'undefined' && mapObject)
                             ? String(mapObject.mapBackground) : null"""),
                "state": page.inner_text("#battlemapImageState"),
                "alerts": alerts,
                "modalGone": page.evaluate("() => !document.getElementById('modalBackground')"),
            }
            page.close()
        return results
    finally:
        context.close()


class TestUploadingABattlemapImage:
    """Choosing an image has to either work or say why not."""

    def test_an_ordinary_battlemap_uploads(self, uploads):
        """Three megabytes is unremarkable for a battlemap and used to be four
        times over the transport's limit."""
        assert uploads["ordinary"]["background"].startswith("get_image.html")

    def test_the_socket_survives_it(self, uploads):
        """Losing this is what made the page stop responding entirely."""
        assert uploads["ordinary"]["connected"]

    def test_the_gm_is_told_it_worked(self, uploads):
        assert "Image loaded" in uploads["ordinary"]["state"]

    def test_an_ordinary_upload_says_nothing_alarming(self, uploads):
        assert uploads["ordinary"]["alerts"] == []

    def test_an_enormous_image_is_refused(self, uploads):
        assert uploads["enormous"]["background"] == "static/images/mapbackground.jpg"

    def test_the_refusal_is_explained(self, uploads):
        assert uploads["enormous"]["alerts"]
        assert "too large" in uploads["enormous"]["alerts"][0]

    def test_the_reason_stays_on_screen(self, uploads):
        """The alert is dismissed; the panel still has to say what happened."""
        assert "too large" in uploads["enormous"]["state"]

    def test_the_socket_survives_a_refusal_too(self, uploads):
        """Refused before sending, so nothing reaches the transport."""
        assert uploads["enormous"]["connected"]

    def test_the_modal_closes_either_way(self, uploads):
        assert uploads["ordinary"]["modalGone"]
        assert uploads["enormous"]["modalGone"]


class TestResizingDuringSetup:
    """The square count is adjustable throughout setup, because it is rarely
    obvious until the grid is sitting on the artwork."""

    def test_the_nudge_button_grows_the_grid(self, battlemap):
        assert battlemap["nudgedGrid"]["after"]["gridAcross"] == 23

    def test_it_leaves_the_other_side_alone(self, battlemap):
        assert battlemap["nudgedGrid"]["after"]["gridDown"] == \
            battlemap["nudgedGrid"]["before"]["gridDown"]

    def test_the_image_does_not_move_with_the_grid(self, battlemap):
        """Changing how many squares the map is says nothing about the artwork."""
        before, after = battlemap["nudgedGrid"]["before"], battlemap["nudgedGrid"]["after"]
        assert after["backgroundSize"] == before["backgroundSize"]
        assert after["backgroundPosition"] == before["backgroundPosition"]

    def test_setup_stays_open_through_a_resize(self, battlemap):
        assert battlemap["nudgedGrid"]["after"]["setupOpen"]


@pytest.fixture(scope="module")
def two_gm_tabs(browser, live_server):
    """One game, two GM views of it, each taking a turn at changing the map.

    A GM with the map open on a laptop and a tablet, or two people running the
    game together. Map events were sent to whichever socket had asked rather
    than to the room every GM view joins, so they reached everyone only when
    the acting view happened to be the first one to connect. From any other
    view the map changed on screen for the person who clicked and nowhere
    else -- and the stale tabs went on editing tiles by coordinates that no
    longer existed.
    """
    context = browser.new_context(viewport={"width": 1100, "height": 700})
    try:
        first = context.new_page()
        errors = []
        first.on("pageerror", lambda error: errors.append(str(error)))
        first.goto(live_server + "/")
        first.wait_for_function(
            "() => typeof socket !== 'undefined' && socket !== null && socket.connected",
            timeout=HANDSHAKE_TIMEOUT,
        )
        first.fill("#gameName", "two tabs")
        first.click("text=Create Game")
        first.wait_for_url("**/gm.html*", timeout=HANDSHAKE_TIMEOUT)
        first.wait_for_selector("#mapForm", state="attached")

        second = context.new_page()
        second.on("pageerror", lambda error: errors.append(str(error)))
        second.goto(first.url)
        second.wait_for_function(
            "() => typeof socket !== 'undefined' && socket !== null && socket.connected",
            timeout=HANDSHAKE_TIMEOUT,
        )
        second.wait_for_selector("#mapForm", state="attached")

        def tiles(page):
            return page.eval_on_selector_all("#mapGraphic .mapTile", "els => els.length")

        def generate(page, width, height):
            """Send what the Generate Map form sends.

            The form itself is only on screen while the map is blank, so once a
            tab has a map -- which is the state this fixture is testing for --
            there is no button left to click.
            """
            page.evaluate(
                """([w, h]) => socket.emit("map_generate", {room: room, gmKey: gmKey,
                     mapWidth: w, mapHeight: h, discovered: false})""",
                [width, height],
            )

        stages = {}

        # The first tab acts. This is the case that always worked, because the
        # room the events went to is named after this tab's socket.
        first.fill("#mapWidth", "5")
        first.fill("#mapHeight", "4")
        first.click("text=Generate Map")
        first.wait_for_function(
            "() => document.querySelectorAll('#mapGraphic .mapTile').length === 20",
            timeout=HANDSHAKE_TIMEOUT,
        )
        second.wait_for_timeout(500)
        stages["firstActed"] = {"first": tiles(first), "second": tiles(second)}

        # The second tab acts. This is the case that did not.
        generate(second, 3, 3)
        second.wait_for_function(
            "() => document.querySelectorAll('#mapGraphic .mapTile').length === 9",
            timeout=HANDSHAKE_TIMEOUT,
        )
        first.wait_for_timeout(500)
        stages["secondActed"] = {"first": tiles(first), "second": tiles(second)}

        # A tile edit from the second tab, which travels as a partial update
        # rather than a whole map.
        second.evaluate(
            """() => socket.emit("map_edit", {room: room, gmKey: gmKey,
                 tiles: [{xCoord: 1, yCoord: 1, newTile: "wallTile"}]})"""
        )
        first.wait_for_timeout(500)

        def tile_kind(page):
            return page.evaluate(
                """() => mapObject.mapArray[1][1].tile"""
            )

        stages["edited"] = {"first": tile_kind(first), "second": tile_kind(second)}
        stages["errors"] = errors
        return stages
    finally:
        context.close()


class TestTwoGmTabs:
    def test_the_first_tab_sees_its_own_map(self, two_gm_tabs):
        assert two_gm_tabs["firstActed"]["first"] == 20

    def test_the_second_tab_sees_the_first_tabs_map(self, two_gm_tabs):
        assert two_gm_tabs["firstActed"]["second"] == 20

    def test_the_second_tab_sees_its_own_map(self, two_gm_tabs):
        assert two_gm_tabs["secondActed"]["second"] == 9

    def test_the_first_tab_sees_the_second_tabs_map(self, two_gm_tabs):
        """The failure: the first tab stayed on a 20-tile map that no longer
        existed on the server."""
        assert two_gm_tabs["secondActed"]["first"] == 9

    def test_a_tile_edit_from_the_second_tab_reaches_the_first(self, two_gm_tabs):
        assert two_gm_tabs["edited"]["first"] == "wallTile"

    def test_nothing_raised(self, two_gm_tabs):
        assert two_gm_tabs["errors"] == []


# A player is in the unit list too, so everything here counts the creatures
# that were added by name rather than counting the list.
ENCOUNTER_REPORT_JS = """
(name) => ({
  initiativeLabel: document.getElementById("unitInitLabel").innerText,
  listedNames: Array.from(document.getElementById("unitsDiv").children)
    .map(entry => entry.innerText.trim().split("\\n")[0]),
  added: (typeof gmData !== "undefined" && gmData)
    ? gmData.unitList.filter(unit => unit.charName === name) : [],
  initiatives: (typeof gmData !== "undefined" && gmData)
    ? gmData.initiativeList.filter(unit => unit.charName === name)
        .map(unit => Number(unit.initiative)) : [],
  tokenField: document.getElementById("unitToken").value,
  tokenPreviewShown: document.getElementById("unitTokenPreview").style.display !== "none",
  countField: document.getElementById("unitCount").value,
  chat: document.getElementById("chatText").innerText,
})
"""


@pytest.fixture(scope="module")
def encounter(browser, live_server, tmp_path_factory):
    """Add a group of creatures at once, with an uploaded token, and watch.

    Six goblins used to be six trips through this form, and the initiative
    field wanted the finished count -- a number six creatures cannot share --
    so the rolling happened somewhere else and was typed back in six times.
    """
    token_file = write_blob(tmp_path_factory.mktemp("tokens") / "goblin.png", 2048)

    context = browser.new_context(viewport={"width": 1400, "height": 900})
    try:
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(live_server + "/")
        page.wait_for_function(
            "() => typeof socket !== 'undefined' && socket !== null && socket.connected",
            timeout=HANDSHAKE_TIMEOUT,
        )
        page.fill("#gameName", "encounter")
        page.click("text=Create Game")
        page.wait_for_url("**/gm.html*", timeout=HANDSHAKE_TIMEOUT)
        page.wait_for_selector("#mapForm", state="attached")
        room = dict(pair.split("=", 1) for pair in page.url.split("?", 1)[1].split("&"))["room"]

        # A player, to check the rolls stop at the GM. Joined before anything
        # is added, so it is listening the whole time.
        player = context.new_page()
        player.goto("%s/player.html?room=%s&charName=Aria" % (live_server, room))
        player.wait_for_function(
            "() => typeof socket !== 'undefined' && socket !== null && socket.connected",
            timeout=HANDSHAKE_TIMEOUT,
        )

        page.click("div.tab:text-is('Encounter')")
        page.wait_for_selector("#unitCount", state="visible")
        stages = {"opened": page.evaluate(ENCOUNTER_REPORT_JS, "Goblin")}

        page.fill("#unitCount", "6")
        page.dispatch_event("#unitCount", "change")
        stages["multipleRequested"] = page.evaluate(ENCOUNTER_REPORT_JS, "Goblin")

        page.click("text=Choose Token")
        page.wait_for_selector("#imageFileUpload")
        page.set_input_files("#imageFileUpload", token_file)
        page.click('#modalBackground button:has-text("Select")')
        page.wait_for_function(
            "() => document.getElementById('unitToken').value.startsWith('data:image')",
            timeout=HANDSHAKE_TIMEOUT,
        )
        stages["tokenChosen"] = page.evaluate(ENCOUNTER_REPORT_JS, "Goblin")

        page.fill("#unitName", "Goblin")
        page.fill("#unitInit", "+3")
        page.fill("#unitHP", "6")
        page.set_checked("#addToInit", True)
        page.click("text=Add Unit")
        page.wait_for_function(
            """() => gmData &&
                 gmData.unitList.filter(unit => unit.charName === "Goblin").length === 6""",
            timeout=HANDSHAKE_TIMEOUT,
        )
        page.wait_for_timeout(500)
        stages["added"] = page.evaluate(ENCOUNTER_REPORT_JS, "Goblin")

        # One creature, whose initiative the GM already knows.
        page.fill("#unitName", "Boss")
        page.fill("#unitInit", "17")
        page.fill("#unitHP", "60")
        page.click("text=Add Unit")
        page.wait_for_function(
            """() => gmData &&
                 gmData.unitList.some(unit => unit.charName === "Boss")""",
            timeout=HANDSHAKE_TIMEOUT,
        )
        page.wait_for_timeout(500)
        stages["singleAdded"] = page.evaluate(ENCOUNTER_REPORT_JS, "Boss")

        stages["playerChat"] = player.inner_text("#chatText")
        stages["errors"] = errors
        return stages
    finally:
        context.close()


class TestAddingAGroupOfCreatures:
    def test_the_field_asks_for_a_count_for_one_creature(self, encounter):
        assert encounter["opened"]["initiativeLabel"] == "Initiative Count"

    def test_the_field_asks_for_a_bonus_for_several(self, encounter):
        """Six creatures cannot share one initiative count, so above one copy
        the same box means the modifier they each roll against."""
        assert "Bonus" in encounter["multipleRequested"]["initiativeLabel"]

    def test_all_six_are_added_at_once(self, encounter):
        assert len(encounter["added"]["added"]) == 6

    def test_they_all_reach_the_gm_unit_list(self, encounter):
        listed = [name for name in encounter["added"]["listedNames"] if name == "Goblin"]
        assert listed == ["Goblin"] * 6

    def test_they_all_reach_the_initiative_order(self, encounter):
        assert len(encounter["added"]["initiatives"]) == 6

    def test_they_rolled_separately(self, encounter):
        """One roll shared out is the thing this replaces."""
        assert len(set(encounter["added"]["initiatives"])) > 1

    def test_the_rolls_are_a_d20_plus_the_typed_bonus(self, encounter):
        assert all(4 <= score <= 23 for score in encounter["added"]["initiatives"])

    def test_the_order_is_sorted_by_the_rolls(self, encounter):
        scores = encounter["added"]["initiatives"]
        assert scores == sorted(scores, reverse=True)

    def test_a_single_creature_still_takes_an_exact_count(self, encounter):
        assert [unit["initiative"] for unit in encounter["singleAdded"]["added"]] == ["17"]

    def test_the_form_resets_to_one(self, encounter):
        """Otherwise the next creature quietly arrives six times."""
        assert encounter["added"]["countField"] == "1"
        assert encounter["added"]["initiativeLabel"] == "Initiative Count"


class TestUploadingATokenForTheGroup:
    def test_choosing_a_file_fills_the_token_field(self, encounter):
        assert encounter["tokenChosen"]["tokenField"].startswith("data:image")

    def test_the_gm_can_see_what_they_picked(self, encounter):
        """The field holds the whole image as a data URI, which tells the GM
        nothing about it."""
        assert encounter["tokenChosen"]["tokenPreviewShown"]

    def test_every_creature_wears_it(self, encounter):
        tokens = [unit["token"] for unit in encounter["added"]["added"]]
        assert len(tokens) == 6
        assert all(token.startswith("get_image.html") for token in tokens)

    def test_they_share_one_stored_image(self, encounter):
        """Six copies of the same token would go into every autosave six
        times."""
        assert len({unit["token"] for unit in encounter["added"]["added"]}) == 1

    def test_the_field_clears_for_the_next_creature(self, encounter):
        assert encounter["singleAdded"]["tokenField"] == ""
        assert not encounter["singleAdded"]["tokenPreviewShown"]


class TestWhoSeesTheRolls:
    def test_the_gm_is_shown_the_breakdown(self, encounter):
        assert "Goblin initiative:" in encounter["added"]["chat"]
        assert encounter["added"]["chat"].count("d20(") == 6

    def test_the_players_are_not(self, encounter):
        """Which goblin rolled a 2 is not the party's business."""
        assert "initiative:" not in encounter["playerChat"]

    def test_a_single_creature_adds_no_line(self, encounter):
        """Nothing was rolled, so there is nothing to report."""
        assert encounter["singleAdded"]["chat"].count("initiative:") == 1


class TestTheEncounterFormStillWorks:
    def test_nothing_raised(self, encounter):
        assert encounter["errors"] == []


LIGHT_PROBE_JS = """
(xy) => {
  const [x, y] = xy;
  const tile = document.getElementById(`tile${x},${y}`);
  const wash = document.getElementById(`light${x},${y}`);
  return {
    tileBackground: tile.style.background,
    tileOpacity: getComputedStyle(tile).opacity,
    tileClass: tile.className,
    washClass: wash ? wash.className : null,
    washColor: wash ? getComputedStyle(wash).backgroundColor : null,
    washPointerEvents: wash ? getComputedStyle(wash).pointerEvents : null,
    washDisplay: wash ? getComputedStyle(wash).display : null,
    washZ: wash ? getComputedStyle(wash).zIndex : null,
    tileZ: getComputedStyle(tile).zIndex,
    washCount: document.querySelectorAll("#mapGraphic .lightWash").length,
  };
}
"""

LIGHT_LIST_JS = """
() => Array.from(document.querySelectorAll("#mapGraphic .lightWash"))
       .map(element => element.id + ":" + element.className).sort()
"""


def paint_square(page, tool, x, y):
    """Pick a tool from the palette and click a square, as a GM does."""
    page.click("#" + tool)
    page.click('[id="tile%d,%d"]' % (x, y))


@pytest.fixture(scope="module")
def lighting(browser, live_server):
    """Paint light levels through the real palette and measure what happens.

    Light is a wash over the square, and this codebase has already learned the
    hard way what a wash must not do: the tile's background belongs to its type
    and the tile's opacity belongs to Show Features, so an overlay that touches
    either one erases what the tile was drawing or vanishes with the feature
    layer. Everything below is that lesson applied to a second overlay.
    """
    context = browser.new_context(viewport={"width": 1500, "height": 950})
    try:
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(live_server + "/")
        page.wait_for_function(
            "() => typeof socket !== 'undefined' && socket !== null && socket.connected",
            timeout=HANDSHAKE_TIMEOUT,
        )
        page.fill("#gameName", "lighting")
        page.click("text=Create Game")
        page.wait_for_url("**/gm.html*", timeout=HANDSHAKE_TIMEOUT)
        page.wait_for_selector("#mapForm", state="attached")

        page.fill("#mapWidth", "5")
        page.fill("#mapHeight", "4")
        page.click("text=Generate Map")
        page.wait_for_function(
            "() => document.querySelectorAll('#mapGraphic .mapTile').length === 20",
            timeout=HANDSHAKE_TIMEOUT,
        )
        stages = {"unlit": page.evaluate(LIGHT_PROBE_JS, [1, 1])}

        paint_square(page, "lightDim", 1, 1)
        page.wait_for_function(
            "() => document.getElementById('light1,1') !== null",
            timeout=HANDSHAKE_TIMEOUT,
        )
        stages["dim"] = page.evaluate(LIGHT_PROBE_JS, [1, 1])

        # Paint a wall underneath. Proves the wash does not swallow the click,
        # and that a redraw of the tile keeps the wash.
        paint_square(page, "wallTile", 1, 1)
        page.wait_for_function(
            """() => document.getElementById("tile1,1").className.includes("wallTile")""",
            timeout=HANDSHAKE_TIMEOUT,
        )
        stages["wallUnderneath"] = page.evaluate(LIGHT_PROBE_JS, [1, 1])

        paint_square(page, "lightBright", 0, 0)
        paint_square(page, "lightDarkness", 2, 2)
        page.wait_for_function(
            "() => document.querySelectorAll('#mapGraphic .lightWash').length === 3",
            timeout=HANDSHAKE_TIMEOUT,
        )
        stages["bright"] = page.evaluate(LIGHT_PROBE_JS, [0, 0])
        stages["darkness"] = page.evaluate(LIGHT_PROBE_JS, [2, 2])

        # Back to normal light: the element has to go, not merely turn clear.
        paint_square(page, "lightNormal", 1, 1)
        page.wait_for_function(
            "() => document.getElementById('light1,1') === null",
            timeout=HANDSHAKE_TIMEOUT,
        )
        stages["backToNormal"] = page.evaluate(LIGHT_PROBE_JS, [1, 1])

        page.set_checked("#showLight", False)
        page.wait_for_timeout(300)
        stages["lightHidden"] = page.evaluate(LIGHT_PROBE_JS, [0, 0])
        page.set_checked("#showLight", True)
        page.wait_for_timeout(300)
        stages["lightShown"] = page.evaluate(LIGHT_PROBE_JS, [0, 0])

        # The discovered overlay redraws the whole map when it is toggled.
        page.set_checked("#seenOverlay", False)
        page.wait_for_timeout(400)
        stages["overlayOff"] = page.evaluate(LIGHT_PROBE_JS, [0, 0])
        page.set_checked("#seenOverlay", True)
        page.wait_for_timeout(400)
        stages["overlayOn"] = page.evaluate(LIGHT_PROBE_JS, [0, 0])

        # Show Features drives the tile's own opacity to zero.
        page.set_checked("#showFeatures", False)
        page.wait_for_timeout(400)
        stages["featuresOff"] = page.evaluate(LIGHT_PROBE_JS, [0, 0])
        page.set_checked("#showFeatures", True)
        page.wait_for_timeout(400)

        # And over an uploaded battlemap, where the tile is fully transparent.
        page.evaluate(
            """(url) => socket.emit("image_upload", room, url, "mapBackground", "")""",
            "https://example.invalid/cavern.png",
        )
        page.wait_for_timeout(1200)
        page.evaluate("() => drawMap(mapObject)")
        page.wait_for_timeout(400)
        stages["overBattlemap"] = page.evaluate(LIGHT_PROBE_JS, [0, 0])

        stages["errors"] = errors
        return stages
    finally:
        context.close()


class TestPaintingLightLevels:
    def test_a_fresh_square_has_no_wash(self, lighting):
        assert lighting["unlit"]["washClass"] is None

    def test_painting_dim_adds_one(self, lighting):
        assert lighting["dim"]["washClass"] == "lightWash lightDim"

    def test_bright_and_darkness_are_told_apart(self, lighting):
        assert lighting["bright"]["washClass"] == "lightWash lightBright"
        assert lighting["darkness"]["washClass"] == "lightWash lightDarkness"
        assert lighting["bright"]["washColor"] != lighting["darkness"]["washColor"]

    def test_the_dark_levels_are_told_apart_from_each_other(self, lighting):
        assert lighting["dim"]["washColor"] != lighting["darkness"]["washColor"]

    def test_the_wash_is_stacked_above_the_tile(self, lighting):
        """The one thing measuring classes and colours does not catch. Behind
        the tile -- where the undiscovered wash sits -- a dark tint is filtered
        through a tile that is 0.6 opaque, and even solid black comes out
        mid-grey. Dim and darkness were indistinguishable on screen while every
        other assertion here passed."""
        assert int(lighting["darkness"]["washZ"]) > int(lighting["darkness"]["tileZ"])

    def test_painting_normal_removes_the_element(self, lighting):
        """Not merely makes it transparent -- a stale overlay div outlives
        every redraw, which is a bug this map has had before."""
        assert lighting["backToNormal"]["washClass"] is None
        assert lighting["backToNormal"]["washCount"] == 2


class TestTheLightWashLeavesTheTileAlone:
    """The rule the discovered overlay took four attempts to learn."""

    def test_it_does_not_touch_the_tiles_background(self, lighting):
        """Floors, doors, stairs and thin walls all paint through it."""
        assert lighting["dim"]["tileBackground"] == lighting["unlit"]["tileBackground"]

    def test_it_does_not_touch_the_tiles_opacity(self, lighting):
        """That belongs to Show Features."""
        assert lighting["dim"]["tileOpacity"] == lighting["unlit"]["tileOpacity"]

    def test_it_does_not_touch_the_tiles_classes(self, lighting):
        assert lighting["dim"]["tileClass"] == lighting["unlit"]["tileClass"]

    def test_it_does_not_swallow_clicks(self, lighting):
        """The GM has to be able to paint the terrain under a dark cavern."""
        assert lighting["dim"]["washPointerEvents"] == "none"
        assert "wallTile" in lighting["wallUnderneath"]["tileClass"]

    def test_the_wash_survives_the_tile_being_repainted(self, lighting):
        """updateMap replaces the tile element; the wash has to come back."""
        assert lighting["wallUnderneath"]["washClass"] == "lightWash lightDim"

    def test_no_wash_is_left_behind(self, lighting):
        assert lighting["overBattlemap"]["washCount"] == 2


class TestLightComposesWithTheOtherOverlays:
    def test_the_discovered_overlay_redraw_keeps_the_light(self, lighting):
        assert lighting["overlayOff"]["washClass"] == "lightWash lightBright"
        assert lighting["overlayOn"]["washClass"] == "lightWash lightBright"

    def test_show_features_does_not_take_the_light_with_it(self, lighting):
        """It hides the feature layer by zeroing the tile's opacity. Anything
        living on the tile goes with it; this does not live on the tile."""
        assert lighting["featuresOff"]["tileOpacity"] == "0"
        assert lighting["featuresOff"]["washClass"] == "lightWash lightBright"

    def test_the_tint_lands_over_an_uploaded_battlemap(self, lighting):
        """Where the tile itself is fully transparent, so the wash is tinting
        the artwork rather than the tile."""
        assert lighting["overBattlemap"]["tileOpacity"] == "0"
        assert lighting["overBattlemap"]["washClass"] == "lightWash lightBright"


class TestTheShowLightSwitch:
    def test_it_hides_the_tint(self, lighting):
        assert lighting["lightHidden"]["washDisplay"] == "none"

    def test_it_leaves_the_elements_alone(self, lighting):
        """One class on the map, so there is nothing to fall out of step."""
        assert lighting["lightHidden"]["washCount"] == 2

    def test_it_brings_the_tint_back(self, lighting):
        assert lighting["lightShown"]["washDisplay"] == "block"


class TestLightingRaisedNothing:
    def test_nothing_raised(self, lighting):
        assert lighting["errors"] == []


@pytest.fixture(scope="module")
def lit_player_view(browser, live_server):
    """What a player is shown of the GM's lighting.

    The level of a square nobody has explored would draw the shape of the room
    through the fog, which is what the fog is for.
    """
    context = browser.new_context(viewport={"width": 1400, "height": 900})
    try:
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append("gm: " + str(error)))
        page.goto(live_server + "/")
        page.wait_for_function(
            "() => typeof socket !== 'undefined' && socket !== null && socket.connected",
            timeout=HANDSHAKE_TIMEOUT,
        )
        page.fill("#gameName", "lit player view")
        page.click("text=Create Game")
        page.wait_for_url("**/gm.html*", timeout=HANDSHAKE_TIMEOUT)
        page.wait_for_selector("#mapForm", state="attached")
        room = dict(pair.split("=", 1) for pair in page.url.split("?", 1)[1].split("&"))["room"]

        page.fill("#mapWidth", "5")
        page.fill("#mapHeight", "4")
        page.click("text=Generate Map")
        page.wait_for_function(
            "() => document.querySelectorAll('#mapGraphic .mapTile').length === 20",
            timeout=HANDSHAKE_TIMEOUT,
        )
        # Discover everything except the far corner, which stays unexplored.
        page.evaluate(
            """() => { for (let y = 0; y < 4; y++) for (let x = 0; x < 5; x++) {
                 if (x === 4 && y === 0) continue;
                 socket.emit("map_edit", {room: room, gmKey: gmKey,
                   tiles: [{newTile: "seen", xCoord: x, yCoord: y}]});
               } }"""
        )
        page.wait_for_timeout(1500)

        paint_square(page, "lightDarkness", 1, 1)
        paint_square(page, "lightBright", 3, 3)
        paint_square(page, "lightDarkness", 4, 0)   # the unexplored square
        page.wait_for_timeout(800)
        stages = {"gm": page.evaluate(LIGHT_LIST_JS)}

        player = context.new_page()
        player.on("pageerror", lambda error: errors.append("player: " + str(error)))
        player.goto("%s/player.html?room=%s&charName=Aria" % (live_server, room))
        player.wait_for_function(
            "() => typeof socket !== 'undefined' && socket !== null && socket.connected",
            timeout=HANDSHAKE_TIMEOUT,
        )
        player.wait_for_function(
            "() => document.querySelectorAll('#mapGraphic .lightWash').length > 0",
            timeout=HANDSHAKE_TIMEOUT,
        )
        stages["playerOnJoin"] = player.evaluate(LIGHT_LIST_JS)

        # A paint made while the player is watching.
        paint_square(page, "lightDim", 0, 0)
        player.wait_for_function(
            "() => document.getElementById('light0,0') !== null",
            timeout=HANDSHAKE_TIMEOUT,
        )
        stages["playerAfterLivePaint"] = player.evaluate(LIGHT_LIST_JS)
        # Waited for separately: the GM page is in the background now that the
        # player page exists, and a backgrounded tab is throttled enough that
        # it can still be a beat behind one that is on screen.
        page.wait_for_function(
            "() => document.getElementById('light0,0') !== null",
            timeout=HANDSHAKE_TIMEOUT,
        )
        stages["gmAfterLivePaint"] = page.evaluate(LIGHT_LIST_JS)

        # The player's own Show light switch, and whether it is genuinely their
        # own -- two people looking at the same room should be able to disagree
        # about whether they want the tint painted.
        display = """(id) => getComputedStyle(document.getElementById(id)).display"""
        # Where the switch actually landed, not merely whether it rendered.
        # Anchored to the bottom of the map area it sat six pixels below the
        # fold, which is invisible to a player and invisible to is_visible.
        stages["switchBox"] = player.locator("#playerMapTools").bounding_box()
        stages["viewport"] = player.viewport_size
        stages["playerLightOn"] = player.evaluate(display, "light1,1")
        player.set_checked("#showLight", False)
        player.wait_for_timeout(300)
        stages["playerLightOff"] = player.evaluate(display, "light1,1")
        stages["playerWashesKept"] = len(player.evaluate(LIGHT_LIST_JS))
        stages["gmUnaffected"] = page.evaluate(display, "light1,1")
        player.set_checked("#showLight", True)
        player.wait_for_timeout(300)
        stages["playerLightBack"] = player.evaluate(display, "light1,1")

        page.set_checked("#showLight", False)
        page.wait_for_timeout(300)
        stages["gmOff"] = page.evaluate(display, "light1,1")
        stages["playerUnaffected"] = player.evaluate(display, "light1,1")

        stages["errors"] = errors
        return stages
    finally:
        context.close()


class TestWhatThePlayersSeeOfTheLight:
    def test_the_gm_painted_four_squares(self, lit_player_view):
        assert len(lit_player_view["gmAfterLivePaint"]) == 4

    def test_the_player_is_shown_the_explored_ones(self, lit_player_view):
        assert "light1,1:lightWash lightDarkness" in lit_player_view["playerOnJoin"]
        assert "light3,3:lightWash lightBright" in lit_player_view["playerOnJoin"]

    def test_the_player_is_not_shown_the_unexplored_one(self, lit_player_view):
        """It would draw the shape of a room nobody has been in."""
        assert "light4,0:lightWash lightDarkness" in lit_player_view["gm"]
        assert not any("light4,0" in wash for wash in lit_player_view["playerOnJoin"])

    def test_a_live_paint_reaches_the_player(self, lit_player_view):
        assert "light0,0:lightWash lightDim" in lit_player_view["playerAfterLivePaint"]

    def test_the_two_views_differ_by_exactly_the_unexplored_square(self, lit_player_view):
        assert len(lit_player_view["gmAfterLivePaint"]) == 4
        assert len(lit_player_view["playerAfterLivePaint"]) == 3

    def test_nothing_raised(self, lit_player_view):
        assert lit_player_view["errors"] == []


class TestThePlayersOwnShowLightSwitch:
    """Players get the same switch the GM has, over the top-right of their map.

    It hides nothing they were not already sent -- the levels are on their
    client either way -- so it is a view preference, not a server round trip,
    and one person turning it off tells the rest of the table nothing.
    """

    def test_the_switch_is_actually_on_screen(self, lit_player_view):
        """A control below the fold still reports visible, still answers a
        click from a test, and cannot be found by a person."""
        box, viewport = lit_player_view["switchBox"], lit_player_view["viewport"]
        assert 0 <= box["x"] and box["x"] + box["width"] <= viewport["width"]
        assert 0 <= box["y"] and box["y"] + box["height"] <= viewport["height"]

    def test_the_tint_is_painted_by_default(self, lit_player_view):
        assert lit_player_view["playerLightOn"] == "block"

    def test_the_player_can_turn_it_off(self, lit_player_view):
        assert lit_player_view["playerLightOff"] == "none"

    def test_turning_it_off_keeps_the_elements(self, lit_player_view):
        assert lit_player_view["playerWashesKept"] == 3

    def test_the_player_can_turn_it_back_on(self, lit_player_view):
        assert lit_player_view["playerLightBack"] == "block"

    def test_the_players_switch_does_not_reach_the_gm(self, lit_player_view):
        assert lit_player_view["gmUnaffected"] == "block"

    def test_the_gms_switch_does_not_reach_the_player(self, lit_player_view):
        assert lit_player_view["gmOff"] == "none"
        assert lit_player_view["playerUnaffected"] == "block"


@pytest.fixture(scope="module")
def vision_checkboxes(browser, live_server):
    """Tick Darkvision on a creature and see whether it stays ticked.

    It did not. The checkbox was on the sheet, updateChar put it on the wire
    and the handler assigned it, but the field was in neither Unit's
    constructor nor its to_json -- so the value reached no client, and the very
    next gm_update repainted the sheet from a unit that had never heard of it.
    """
    context = browser.new_context(viewport={"width": 1400, "height": 900})
    try:
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(live_server + "/")
        page.wait_for_function(
            "() => typeof socket !== 'undefined' && socket !== null && socket.connected",
            timeout=HANDSHAKE_TIMEOUT,
        )
        page.fill("#gameName", "vision")
        page.click("text=Create Game")
        page.wait_for_url("**/gm.html*", timeout=HANDSHAKE_TIMEOUT)
        page.wait_for_selector("#mapForm", state="attached")

        page.click("div.tab:text-is('Encounter')")
        page.wait_for_selector("#unitName", state="visible")
        page.fill("#unitName", "Grimlock")
        page.click("text=Add Unit")
        page.wait_for_function(
            """() => gmData && gmData.unitList.some(unit => unit.charName === "Grimlock")""",
            timeout=HANDSHAKE_TIMEOUT,
        )

        # The sheet lives in the Units tab, and populateEditChar only fills it
        # in while that tab is closed -- so open it after selecting.
        page.evaluate("() => selectUnit({shiftKey: false}, 0)")
        page.click("div.tab:text-is('Units')")
        page.wait_for_selector("#darkvision", state="visible")
        page.evaluate("() => populateEditChar(gmData, 0)")
        page.wait_for_timeout(400)
        stages = {"beforeTicking": page.is_checked("#darkvision")}

        page.set_checked("#darkvision", True)
        page.set_checked("#lowLight", True)
        page.click("#updateCharButton")
        # The update comes back as gm_update, which repaints the sheet. That
        # repaint is what used to undo it.
        page.wait_for_timeout(1200)
        stages["afterUpdate"] = {
            "darkvision": page.is_checked("#darkvision"),
            "lowLight": page.is_checked("#lowLight"),
        }
        stages["onTheUnit"] = page.evaluate(
            """() => { const u = gmData.unitList.find(x => x.charName === "Grimlock");
                       return {darkvision: u.darkvision, lowLight: u.lowLight}; }"""
        )

        # And it survives the sheet being repainted from scratch.
        page.evaluate("() => populateEditChar(gmData, 0)")
        page.wait_for_timeout(300)
        stages["afterRepopulate"] = page.is_checked("#darkvision")

        stages["errors"] = errors
        return stages
    finally:
        context.close()


class TestVisionCheckboxesStick:
    def test_a_new_creature_has_neither(self, vision_checkboxes):
        assert vision_checkboxes["beforeTicking"] is False

    def test_the_setting_survives_the_update(self, vision_checkboxes):
        assert vision_checkboxes["afterUpdate"]["darkvision"] is True
        assert vision_checkboxes["afterUpdate"]["lowLight"] is True

    def test_it_reached_the_unit_the_client_holds(self, vision_checkboxes):
        """to_json is what gm_update carries; the field used to be missing."""
        assert vision_checkboxes["onTheUnit"]["darkvision"] is True
        assert vision_checkboxes["onTheUnit"]["lowLight"] is True

    def test_it_survives_the_sheet_being_repainted(self, vision_checkboxes):
        assert vision_checkboxes["afterRepopulate"] is True

    def test_nothing_raised(self, vision_checkboxes):
        assert vision_checkboxes["errors"] == []


MONSTER_REPORT_JS = """
(name) => ({
  rows: Array.from(document.querySelectorAll("#creatureRows tr td:first-child"))
    .map(cell => cell.innerText),
  headings: Array.from(document.querySelectorAll(".creatureHeading"))
    .map(cell => cell.innerText),
  crColumn: Array.from(document.querySelectorAll("#creatureRows tr td:nth-child(2)"))
    .map(cell => cell.innerText),
  hpColumn: Array.from(document.querySelectorAll("#creatureRows tr td:nth-child(5)"))
    .map(cell => cell.innerText),
  countText: document.getElementById("creatureSearchCount")
    ? document.getElementById("creatureSearchCount").innerText : "",
  detailLength: document.getElementById("creatureDetail")
    ? document.getElementById("creatureDetail").innerText.length : 0,
  detailHead: document.getElementById("creatureDetail")
    ? document.getElementById("creatureDetail").innerText.slice(0, 40) : "",
  modalOpen: !!document.getElementById("modalBackground"),
  chosenRows: document.querySelectorAll("#creatureRows .creatureRowChosen").length,
  chosenRowName: document.querySelector("#creatureRows .creatureRowChosen td")
    ? document.querySelector("#creatureRows .creatureRowChosen td").innerText : "",
  chosen: document.getElementById("chosenCreature").innerText,
  unitName: document.getElementById("unitName").value,
  unitHP: document.getElementById("unitHP").value,
  unitInit: document.getElementById("unitInit").value,
  initLabel: document.getElementById("unitInitLabel").innerText,
  added: (typeof gmData !== "undefined" && gmData)
    ? gmData.unitList.filter(unit => unit.charName === name) : [],
  chat: document.getElementById("chatText").innerText,
})
"""


@pytest.fixture(scope="module")
def monsters(browser, live_server):
    """Pick a monster out of the database and put seven of them on the board.

    Seven of one creature was seven trips through the encounter form, typing
    the name, the hit points and an initiative that had been rolled somewhere
    else each time.
    """
    context = browser.new_context(viewport={"width": 1500, "height": 950})
    try:
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(live_server + "/")
        page.wait_for_function(
            "() => typeof socket !== 'undefined' && socket !== null && socket.connected",
            timeout=HANDSHAKE_TIMEOUT,
        )
        page.fill("#gameName", "monsters")
        page.click("text=Create Game")
        page.wait_for_url("**/gm.html*", timeout=HANDSHAKE_TIMEOUT)
        page.wait_for_selector("#mapForm", state="attached")
        room = dict(pair.split("=", 1) for pair in page.url.split("?", 1)[1].split("&"))["room"]

        player = context.new_page()
        player.goto("%s/player.html?room=%s&charName=Aria" % (live_server, room))
        player.wait_for_function(
            "() => typeof socket !== 'undefined' && socket !== null && socket.connected",
            timeout=HANDSHAKE_TIMEOUT,
        )

        page.click("div.tab:text-is('Encounter')")
        page.wait_for_selector("#chooseMonsterButton", state="visible")
        stages = {"before": page.evaluate(MONSTER_REPORT_JS, "Dire Ape")}

        page.click("#chooseMonsterButton")
        page.wait_for_selector("#creatureSearchName")
        page.fill("#creatureSearchName", "dire ape")
        page.wait_for_function(
            "() => document.querySelectorAll('#creatureRows tr').length > 0",
            timeout=HANDSHAKE_TIMEOUT,
        )
        stages["searched"] = page.evaluate(MONSTER_REPORT_JS, "Dire Ape")

        # Filtering narrows the same search rather than starting a new one.
        page.select_option("#creatureSearchType", "dragon")
        page.wait_for_function(
            "() => document.getElementById('creatureSearchCount').innerText.indexOf('No creatures') === 0",
            timeout=HANDSHAKE_TIMEOUT,
        )
        stages["filteredAway"] = page.evaluate(MONSTER_REPORT_JS, "Dire Ape")
        page.select_option("#creatureSearchType", "animal")
        page.wait_for_function(
            "() => document.querySelectorAll('#creatureRows tr').length > 0",
            timeout=HANDSHAKE_TIMEOUT,
        )

        page.click("#creatureRows tr:first-child td:first-child")
        page.wait_for_function(
            "() => document.getElementById('creatureDetail').innerText.length > 100",
            timeout=HANDSHAKE_TIMEOUT,
        )
        stages["detail"] = page.evaluate(MONSTER_REPORT_JS, "Dire Ape")

        page.click("#creatureRows tr:first-child button")
        page.wait_for_function(
            "() => !document.getElementById('modalBackground')", timeout=HANDSHAKE_TIMEOUT)
        stages["picked"] = page.evaluate(MONSTER_REPORT_JS, "Dire Ape")

        page.fill("#unitCount", "7")
        page.set_checked("#addToInit", True)
        page.click("text=Add Unit")
        page.wait_for_function(
            """() => gmData && gmData.unitList.filter(u => u.charName === "Dire Ape").length === 7""",
            timeout=HANDSHAKE_TIMEOUT,
        )
        page.wait_for_timeout(600)
        stages["added"] = page.evaluate(MONSTER_REPORT_JS, "Dire Ape")
        player.wait_for_timeout(400)
        stages["playerChat"] = player.inner_text("#chatText")

        # The column headings, which re-run the search rather than reordering
        # the rows already here -- the result is capped, so those are not the
        # same thing.
        page.click("#chooseMonsterButton")
        page.wait_for_selector("#creatureSearchName")
        page.fill("#creatureSearchName", "dragon")
        page.wait_for_function(
            "() => document.querySelectorAll('#creatureRows tr').length > 0",
            timeout=HANDSHAKE_TIMEOUT,
        )
        stages["byName"] = page.evaluate(MONSTER_REPORT_JS, "Dire Ape")
        page.click(".creatureHeading:nth-child(2)")
        page.wait_for_function(
            """() => document.querySelectorAll('.creatureHeading')[1].innerText.indexOf('\u25b4') !== -1""",
            timeout=HANDSHAKE_TIMEOUT,
        )
        page.wait_for_timeout(400)
        stages["byCR"] = page.evaluate(MONSTER_REPORT_JS, "Dire Ape")
        page.click(".creatureHeading:nth-child(2)")
        page.wait_for_function(
            """() => document.querySelectorAll('.creatureHeading')[1].innerText.indexOf('\u25be') !== -1""",
            timeout=HANDSHAKE_TIMEOUT,
        )
        page.wait_for_timeout(400)
        stages["byCRDescending"] = page.evaluate(MONSTER_REPORT_JS, "Dire Ape")
        page.click(".creatureHeading:nth-child(5)")
        page.wait_for_timeout(700)
        stages["byHP"] = page.evaluate(MONSTER_REPORT_JS, "Dire Ape")
        # A corner of the backdrop: its centre is where the picker sits, and
        # the picker stops the click from reaching it.
        page.click("#modalBackground", position={"x": 5, "y": 5})
        page.wait_for_function(
            "() => !document.getElementById('modalBackground')", timeout=HANDSHAKE_TIMEOUT)

        # Searching repeatedly must not pile up socket listeners, which is what
        # the CR browser this replaced did on every change.
        page.click("#chooseMonsterButton")
        page.wait_for_selector("#creatureSearchName")
        for term in ["goblin", "ogre", "troll", "wolf"]:
            page.fill("#creatureSearchName", term)
            page.wait_for_timeout(350)
        stages["listeners"] = page.evaluate(
            """() => socket._callbacks
                 ? Object.keys(socket._callbacks).filter(
                     k => k.indexOf("database_creature") !== -1).length
                 : 0""")
        stages["errors"] = errors
        return stages
    finally:
        context.close()


class TestSearchingForAMonster:
    def test_the_button_is_on_the_encounter_form(self, monsters):
        assert monsters["before"]["chosen"] == ""

    def test_a_name_search_finds_the_creature(self, monsters):
        assert "Dire Ape" in monsters["searched"]["rows"]

    def test_the_search_is_a_substring(self, monsters):
        assert "Fiendish Dire Ape" in monsters["searched"]["rows"]

    def test_the_result_count_is_reported(self, monsters):
        assert "creature" in monsters["searched"]["countText"]

    def test_a_type_filter_narrows_the_same_search(self, monsters):
        """No apes are dragons."""
        assert monsters["filteredAway"]["rows"] == []
        assert "No creatures" in monsters["filteredAway"]["countText"]

    def test_clicking_a_row_shows_its_statblock(self, monsters):
        assert monsters["detail"]["detailLength"] > 100
        assert monsters["detail"]["detailHead"].startswith("Dire Ape")

    def test_the_clicked_row_stays_marked(self, monsters):
        """Hover alone would leave it unclear which creature the statblock
        below belongs to the moment the mouse moves away."""
        assert monsters["detail"]["chosenRows"] == 1
        assert monsters["detail"]["chosenRowName"] == "Dire Ape"

    def test_only_one_row_is_marked_at_a_time(self, monsters):
        assert monsters["byCR"]["chosenRows"] == 0

    def test_the_columns_all_have_headings(self, monsters):
        assert [h.replace(" \u25b4", "").replace(" \u25be", "")
                for h in monsters["byName"]["headings"]] == \
            ["Name", "CR", "Type", "Size", "HP", "Source"]

    def test_the_sorted_column_is_marked(self, monsters):
        assert "\u25b4" in monsters["byName"]["headings"][0]

    def test_clicking_a_heading_sorts_by_it(self, monsters):
        crs = [float(c) for c in monsters["byCR"]["crColumn"] if "/" not in c]
        assert crs == sorted(crs)

    def test_the_mark_moves_to_the_column_clicked(self, monsters):
        assert "\u25b4" in monsters["byCR"]["headings"][1]
        assert "\u25b4" not in monsters["byCR"]["headings"][0]

    def test_clicking_it_again_turns_it_around(self, monsters):
        crs = [float(c) for c in monsters["byCRDescending"]["crColumn"] if "/" not in c]
        assert crs == sorted(crs, reverse=True)
        assert "\u25be" in monsters["byCRDescending"]["headings"][1]

    def test_hp_sorts_as_a_number(self, monsters):
        """Sorted as text, 9 would come after 500."""
        hp = [float(h) for h in monsters["byHP"]["hpColumn"] if h and h[0].isdigit()]
        assert hp == sorted(hp)

    def test_sorting_asks_the_server_rather_than_shuffling_the_page(self, monsters):
        """The list is capped, so the rows themselves have to change."""
        assert monsters["byCR"]["rows"] != monsters["byName"]["rows"]

    def test_repeated_searches_do_not_pile_up_listeners(self, monsters):
        """The picker this replaced registered one per search, for the life of
        the page."""
        assert monsters["listeners"] <= 1


class TestAddingSevenOfThem:
    def test_choosing_fills_the_form(self, monsters):
        assert monsters["picked"]["unitName"] == "Dire Ape"
        assert monsters["picked"]["unitHP"] == "30"
        assert monsters["picked"]["unitInit"] == "+2"

    def test_the_creature_is_named_on_the_form(self, monsters):
        assert "Dire Ape" in monsters["picked"]["chosen"]

    def test_the_initiative_field_becomes_a_bonus(self, monsters):
        """A statblock gives a modifier, never a finished count -- and that is
        true for one creature as much as for seven."""
        assert "Bonus" in monsters["picked"]["initLabel"]

    def test_seven_are_added(self, monsters):
        assert len(monsters["added"]["added"]) == 7

    def test_they_rolled_separately(self, monsters):
        initiatives = {unit["initiative"] for unit in monsters["added"]["added"]}
        assert len(initiatives) > 1

    def test_the_rolls_used_the_creatures_bonus(self, monsters):
        assert all(3 <= int(unit["initiative"]) <= 22
                   for unit in monsters["added"]["added"])

    def test_they_carry_the_statblock(self, monsters):
        ape = monsters["added"]["added"][0]
        assert ape["HP"] == 30
        assert ape["size"] == "large"
        assert ape["lowLight"] is True
        assert ape["perception"] == 8

    def test_they_are_mobs_not_animals(self, monsters):
        """Unit.type is the role on the map, not the bestiary type."""
        assert all(unit["type"] == "Mob" for unit in monsters["added"]["added"])

    def test_the_gm_is_shown_the_rolls(self, monsters):
        assert "Dire Ape initiative:" in monsters["added"]["chat"]

    def test_the_players_are_not(self, monsters):
        assert "initiative:" not in monsters["playerChat"]

    def test_the_form_is_cleared_for_the_next_creature(self, monsters):
        assert monsters["added"]["unitName"] == ""
        assert monsters["added"]["chosen"] == ""

    def test_nothing_raised(self, monsters):
        assert monsters["errors"] == []


STATBLOCK_REPORT_JS = """
() => {
  const block = document.querySelector("#creatureDetail .statblock");
  if (!block) { return null; }
  const text = element => element ? element.innerText.trim() : null;
  return {
    name: text(block.querySelector(".sbName")),
    cr: text(block.querySelector(".sbCR")),
    subtitle: text(block.querySelector(".sbSubtitle")),
    headings: Array.from(block.querySelectorAll(".sbHeading")).map(h => h.innerText.trim()),
    abilityCells: Array.from(block.querySelectorAll(".sbAbility")).map(
      cell => [text(cell.querySelector(".sbAbilityName")), text(cell.querySelector(".sbAbilityScore"))]),
    missingScores: block.querySelectorAll(".sbAbilityNone").length,
    boldLabels: Array.from(block.querySelectorAll(".sbLine b")).map(b => b.innerText.trim()),
    specialAbilities: Array.from(block.querySelectorAll(".sbAbilityEntry")).map(
      entry => entry.innerText.trim().slice(0, 30)),
    specialAbilityNames: Array.from(block.querySelectorAll(".sbAbilityEntry b")).map(
      b => b.innerText.trim()),
    headerIsBarred: getComputedStyle(block.querySelector(".sbHeader")).backgroundColor,
  };
}
"""


@pytest.fixture(scope="module")
def statblock(browser, live_server):
    """The statblock a creature shows when its row is clicked.

    Laid out from the columns, because the rendered version the database
    carried was thirteen megabytes of restating them and the imported half of
    the table had none of it.
    """
    context = browser.new_context(viewport={"width": 1500, "height": 1000})
    try:
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(live_server + "/")
        page.wait_for_function(
            "() => typeof socket !== 'undefined' && socket !== null && socket.connected",
            timeout=HANDSHAKE_TIMEOUT,
        )
        page.fill("#gameName", "statblock")
        page.click("text=Create Game")
        page.wait_for_url("**/gm.html*", timeout=HANDSHAKE_TIMEOUT)
        page.wait_for_selector("#mapForm", state="attached")
        page.click("div.tab:text-is('Encounter')")
        page.click("#chooseMonsterButton")
        page.wait_for_selector("#creatureSearchName")

        # A construct: it has several special abilities, and no Constitution or
        # Intelligence at all, which the ability row has to show as absent
        # rather than as a zero.
        page.fill("#creatureSearchName", "earth elemental construct")
        page.wait_for_function(
            "() => document.querySelectorAll('#creatureRows tr').length > 0",
            timeout=HANDSHAKE_TIMEOUT,
        )
        page.click("#creatureRows tr:first-child td:first-child")
        page.wait_for_function(
            "() => document.querySelector('#creatureDetail .statblock')",
            timeout=HANDSHAKE_TIMEOUT,
        )
        stages = {"construct": page.evaluate(STATBLOCK_REPORT_JS)}
        stages["rowClipped"] = page.evaluate(
            """() => {
                 const list = document.getElementById("creatureList");
                 const row = document.querySelector("#creatureRows tr");
                 return row.getBoundingClientRect().bottom
                        > list.getBoundingClientRect().bottom + 1;
               }""")

        # And one with real prose, which only the bundled half of the table has.
        page.fill("#creatureSearchName", "dire ape")
        page.wait_for_function(
            """() => document.querySelectorAll('#creatureRows tr').length > 0
                 && document.querySelectorAll('#creatureRows tr')[0]
                      .querySelector('td').innerText === 'Dire Ape'""",
            timeout=HANDSHAKE_TIMEOUT,
        )
        page.click("#creatureRows tr:first-child td:first-child")
        page.wait_for_function(
            "() => document.querySelector('#creatureDetail .statblock .sbDescription')",
            timeout=HANDSHAKE_TIMEOUT,
        )
        stages["withProse"] = page.evaluate(STATBLOCK_REPORT_JS)
        stages["prose"] = page.inner_text("#creatureDetail .sbDescription")
        stages["errors"] = errors
        return stages
    finally:
        context.close()


class TestTheStatblockLayout:
    def test_the_name_and_cr_head_it(self, statblock):
        assert statblock["construct"]["name"] == "Earth Elemental Construct"
        assert statblock["construct"]["cr"] == "CR 13"

    def test_the_header_is_a_bar_not_plain_text(self, statblock):
        colour = statblock["construct"]["headerIsBarred"]
        assert colour not in ("rgba(0, 0, 0, 0)", "transparent")

    def test_the_subtitle_says_what_it_is(self, statblock):
        assert statblock["construct"]["subtitle"].startswith("N Huge construct")

    def test_the_subtype_is_not_double_bracketed(self, statblock):
        """Every subtype in the table already carries its own brackets."""
        assert "((" not in statblock["construct"]["subtitle"]

    def test_the_sections_are_in_the_printed_order(self, statblock):
        assert statblock["construct"]["headings"] == [
            "Defence", "Offence", "Statistics", "Ecology", "Special Abilities"]

    def test_the_labels_are_bold_and_inline(self, statblock):
        labels = statblock["construct"]["boldLabels"]
        for expected in ["AC", "hp", "Saves", "Speed", "Melee"]:
            assert expected in labels

    def test_a_section_with_nothing_in_it_is_not_drawn(self, statblock):
        """A Dire Ape's rend is a special attack, not a special ability, so it
        has no Special Abilities section at all -- and an empty heading with a
        rule under it would look like something failed to load."""
        assert "Special Abilities" not in statblock["withProse"]["headings"]
        assert "Defence" in statblock["withProse"]["headings"]


class TestTheAbilityScoreRow:
    def test_all_six_are_shown(self, statblock):
        names = [cell[0] for cell in statblock["construct"]["abilityCells"]]
        assert names == ["STR", "DEX", "CON", "INT", "WIS", "CHA"]

    def test_the_scores_are_the_creatures(self, statblock):
        cells = dict(statblock["construct"]["abilityCells"])
        assert cells["STR"] == "38"
        assert cells["DEX"] == "8"

    def test_a_score_the_creature_lacks_is_marked_absent(self, statblock):
        """A construct has neither Constitution nor Intelligence, and showing
        those as zero would be wrong rather than merely ugly."""
        assert statblock["construct"]["missingScores"] == 2


class TestSpecialAbilitiesInTheStatblock:
    def test_each_one_is_its_own_entry(self, statblock):
        assert len(statblock["construct"]["specialAbilities"]) == 3

    def test_their_names_are_bold(self, statblock):
        assert "Earth Mastery (Ex)" in statblock["construct"]["specialAbilityNames"]

    def test_they_were_one_paragraph_in_the_column(self, statblock):
        """Separated by a single space after a bracket, which is why anchoring
        the split on a double space left this creature as one block."""
        assert "Immunity to Magic (Ex)" in statblock["construct"]["specialAbilityNames"]


class TestProseWhereThereIsAny:
    def test_the_bundled_bestiary_keeps_its_description(self, statblock):
        assert "gigantopithecus" in statblock["prose"]

    def test_the_results_row_is_not_clipped(self, statblock):
        """The list must not be squeezed below its own rows to make room for a
        long statblock."""
        assert statblock["rowClipped"] is False

    def test_nothing_raised(self, statblock):
        assert statblock["errors"] == []


ATTACK_REPORT_JS = """
() => ({
  names: Array.from(document.querySelectorAll("#unitAttacks .attackRow input.attackName"))
    .map(input => input.value),
  bonuses: Array.from(document.querySelectorAll("#unitAttacks .attackRow input.attackBonus"))
    .map(input => input.value),
  damages: Array.from(document.querySelectorAll("#unitAttacks .attackRow input.attackDamage"))
    .map(input => input.value),
  disabled: Array.from(document.querySelectorAll("#unitAttacks .attackRollButton"))
    .map(button => button.disabled),
  chat: document.getElementById("chatText").innerText,
})
"""


@pytest.fixture(scope="module")
def attacks(browser, live_server):
    """Roll a monster's attacks from the GM's unit sheet.

    Seven apes was fourteen hand-typed /roll lines a round, after reading the
    bonuses off the statblock.
    """
    context = browser.new_context(viewport={"width": 1500, "height": 950})
    try:
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(live_server + "/")
        page.wait_for_function(
            "() => typeof socket !== 'undefined' && socket !== null && socket.connected",
            timeout=HANDSHAKE_TIMEOUT,
        )
        page.fill("#gameName", "attacks")
        page.click("text=Create Game")
        page.wait_for_url("**/gm.html*", timeout=HANDSHAKE_TIMEOUT)
        page.wait_for_selector("#mapForm", state="attached")
        room = dict(pair.split("=", 1) for pair in page.url.split("?", 1)[1].split("&"))["room"]

        player = context.new_page()
        player.goto("%s/player.html?room=%s&charName=Aria" % (live_server, room))
        player.wait_for_function(
            "() => typeof socket !== 'undefined' && socket !== null && socket.connected",
            timeout=HANDSHAKE_TIMEOUT,
        )

        page.click("div.tab:text-is('Encounter')")
        page.click("#chooseMonsterButton")
        page.wait_for_selector("#creatureSearchName")
        page.fill("#creatureSearchName", "dire ape")
        page.wait_for_function(
            "() => document.querySelectorAll('#creatureRows tr').length > 0",
            timeout=HANDSHAKE_TIMEOUT,
        )
        page.click("#creatureRows tr:first-child button")
        page.wait_for_function(
            "() => !document.getElementById('modalBackground')", timeout=HANDSHAKE_TIMEOUT)
        page.click("text=Add Unit")
        page.wait_for_function(
            """() => gmData && gmData.unitList.some(u => u.charName === "Dire Ape")""",
            timeout=HANDSHAKE_TIMEOUT,
        )
        page.wait_for_timeout(500)

        # Aria joined first, so the ape is not unit zero.
        page.click("div.tab:text-is('Units')")
        page.wait_for_selector("#unitAttacks", state="visible")
        page.evaluate("""() => populateEditChar(gmData,
            gmData.unitList.find(u => u.charName === "Dire Ape").unitNum)""")
        page.wait_for_function(
            "() => document.querySelectorAll('#unitAttacks .attackRow').length > 0",
            timeout=HANDSHAKE_TIMEOUT,
        )
        stages = {"listed": page.evaluate(ATTACK_REPORT_JS)}

        # The second row is "2 claws", which is two swings from one press.
        page.click("#unitAttacks .attackRow:nth-child(2) .attackRollButton")
        page.wait_for_function(
            """() => document.getElementById("chatText").innerText.indexOf("2 claws") !== -1""",
            timeout=HANDSHAKE_TIMEOUT,
        )
        stages["rolled"] = page.evaluate(ATTACK_REPORT_JS)

        # A bonus corrected by hand is the one that gets rolled.
        page.fill("#unitAttacks .attackRow:first-child input.attackBonus", "+99")
        page.click("#unitAttacks .attackRow:first-child .attackRollButton")
        page.wait_for_function(
            """() => document.getElementById("chatText").innerText.indexOf("+99") !== -1""",
            timeout=HANDSHAKE_TIMEOUT,
        )
        stages["edited"] = page.evaluate(ATTACK_REPORT_JS)

        player.wait_for_timeout(500)
        stages["playerChat"] = player.inner_text("#chatText")

        # And the same rows on the player's own Attack tab.
        player.evaluate("""() => {
            const me = playerData.playerList[charName];
            me.weapons = [["longsword", "+7", "1d8+3", "19-20", "", "", ""]];
            socket.emit("update_player", me);
        }""")
        player.wait_for_timeout(700)
        # showBottomDiv opens the panel its parent lives in, then fills the
        # Attack tab; the rows are unclickable without it.
        player.evaluate("() => showBottomDiv()")
        player.wait_for_function(
            "() => document.querySelectorAll('#bottomAttackDiv .attackRow').length > 0",
            timeout=HANDSHAKE_TIMEOUT,
        )
        stages["playerRows"] = player.eval_on_selector_all(
            "#bottomAttackDiv .attackRow input.attackName", "e => e.map(x => x.value)")
        player.click("#bottomAttackDiv .attackRow:first-child .attackRollButton")
        player.wait_for_function(
            """() => document.getElementById("chatText").innerText.indexOf("longsword") !== -1""",
            timeout=HANDSHAKE_TIMEOUT,
        )
        page.wait_for_timeout(500)
        stages["playerRolled"] = player.inner_text("#chatText")
        stages["gmSawPlayerRoll"] = page.inner_text("#chatText")

        stages["errors"] = errors
        return stages
    finally:
        context.close()


class TestTheAttackPanel:
    def test_the_monsters_attacks_are_listed(self, attacks):
        assert attacks["listed"]["names"] == ["bite", "2 claws"]

    def test_they_carry_their_bonuses(self, attacks):
        assert attacks["listed"]["bonuses"] == ["+6", "+6"]

    def test_they_carry_their_damage(self, attacks):
        assert attacks["listed"]["damages"] == ["1d6+4", "1d4+4"]

    def test_every_row_can_be_rolled(self, attacks):
        assert attacks["listed"]["disabled"] == [False, False]

    def test_the_player_gets_the_same_rows(self, attacks):
        """Built once, in shared.js, from the same Unit.weapons list."""
        assert attacks["playerRows"] == ["longsword"]


class TestRollingFromThePanel:
    def test_a_press_rolls_the_attack(self, attacks):
        assert "Dire Ape" in attacks["rolled"]["chat"]
        assert "d20(" in attacks["rolled"]["chat"]

    def test_it_rolls_damage_too(self, attacks):
        assert "damage" in attacks["rolled"]["chat"]

    def test_two_claws_is_two_swings(self, attacks):
        """One press is a full attack, not a single die."""
        line = [l for l in attacks["rolled"]["chat"].split("\n") if "2 claws" in l][0]
        assert line.count("d20(") == 2

    def test_a_bonus_corrected_by_hand_is_the_one_rolled(self, attacks):
        """Rolling reads the boxes, not the stored weapon, because a statblock
        is sometimes wrong."""
        assert "+99" in attacks["edited"]["chat"]

    def test_a_player_can_roll_their_own_weapon(self, attacks):
        assert "longsword" in attacks["playerRolled"]


class TestWhoSeesTheAttackRolls:
    def test_the_monsters_rolls_stay_with_the_gm(self, attacks):
        """The party finds out whether it hit, not what it needed."""
        assert "Dire Ape" not in attacks["playerChat"]

    def test_a_players_own_roll_is_public(self, attacks):
        assert "longsword" in attacks["gmSawPlayerRoll"]

    def test_nothing_raised(self, attacks):
        assert attacks["errors"] == []


CASTING_REPORT_JS = """
() => ({
  labels: Array.from(document.querySelectorAll("#unitCastings .castingLabel"))
    .map(e => e.innerText),
  spells: Array.from(document.querySelectorAll("#unitCastings .castingSpells"))
    .map(e => e.innerText),
  buttons: document.querySelectorAll("#unitCastings .castingUse").length,
  spent: document.querySelectorAll("#unitCastings .castingRowSpent").length,
  chat: document.getElementById("chatText").innerText,
})
"""


@pytest.fixture(scope="module")
def castings(browser, live_server):
    """Spend an Aboleth's three castings of dominate monster and put them back.

    A monster with a limited spell had nowhere to record that it had used one,
    so the GM kept it on paper.
    """
    context = browser.new_context(viewport={"width": 1500, "height": 1000})
    try:
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(live_server + "/")
        page.wait_for_function(
            "() => typeof socket !== 'undefined' && socket !== null && socket.connected",
            timeout=HANDSHAKE_TIMEOUT,
        )
        page.fill("#gameName", "castings")
        page.click("text=Create Game")
        page.wait_for_url("**/gm.html*", timeout=HANDSHAKE_TIMEOUT)
        page.wait_for_selector("#mapForm", state="attached")
        url = page.url
        room = dict(pair.split("=", 1) for pair in url.split("?", 1)[1].split("&"))["room"]

        player = context.new_page()
        player.goto("%s/player.html?room=%s&charName=Aria" % (live_server, room))
        player.wait_for_function(
            "() => typeof socket !== 'undefined' && socket !== null && socket.connected",
            timeout=HANDSHAKE_TIMEOUT,
        )

        page.click("div.tab:text-is('Encounter')")
        page.click("#chooseMonsterButton")
        page.wait_for_selector("#creatureSearchName")
        page.fill("#creatureSearchName", "aboleth")
        page.wait_for_function(
            "() => document.querySelectorAll('#creatureRows tr').length > 0",
            timeout=HANDSHAKE_TIMEOUT,
        )
        page.click("#creatureRows tr:first-child button")
        page.wait_for_function(
            "() => !document.getElementById('modalBackground')", timeout=HANDSHAKE_TIMEOUT)
        page.click("text=Add Unit")
        page.wait_for_function(
            """() => gmData && gmData.unitList.some(u => u.charName === "Aboleth")""",
            timeout=HANDSHAKE_TIMEOUT,
        )
        page.wait_for_timeout(500)

        def show():
            page.evaluate("""() => populateEditChar(gmData,
                gmData.unitList.find(u => u.charName === "Aboleth").unitNum)""")

        page.click("div.tab:text-is('Units')")
        page.wait_for_selector("#unitCastings", state="visible")
        show()
        page.wait_for_function(
            "() => document.querySelectorAll('#unitCastings .castingRow').length > 0",
            timeout=HANDSHAKE_TIMEOUT,
        )
        stages = {"fresh": page.evaluate(CASTING_REPORT_JS)}

        # No redraw by hand from here on. The GM presses cast with the sheet in
        # front of them, and the panel has to answer on its own -- an earlier
        # version of this test called show() after every press, which is what
        # let the panel not refresh at all.
        def buttons_settle(n):
            page.wait_for_function(
                "(n) => document.querySelectorAll('#unitCastings .castingUse').length === n",
                arg=n, timeout=HANDSHAKE_TIMEOUT)

        page.click("#unitCastings .castingUse")
        buttons_settle(2)
        page.wait_for_function(
            """() => document.getElementById("chatText").innerText.indexOf("2 left") !== -1""",
            timeout=HANDSHAKE_TIMEOUT,
        )
        stages["afterOne"] = page.evaluate(CASTING_REPORT_JS)

        for left in [1, 0]:
            page.click("#unitCastings .castingUse")
            buttons_settle(left)
        stages["spent"] = page.evaluate(CASTING_REPORT_JS)
        player.wait_for_timeout(400)
        stages["playerChat"] = player.inner_text("#chatText")

        # The count lives on the server, so it has to survive the page going
        # away -- which is the thing a browser-side counter would get wrong.
        page.reload()
        page.wait_for_function(
            "() => typeof gmData !== 'undefined' && gmData && gmData.unitList.length > 0",
            timeout=HANDSHAKE_TIMEOUT,
        )
        page.click("div.tab:text-is('Units')")
        show()
        page.wait_for_timeout(400)
        stages["afterReload"] = page.evaluate(CASTING_REPORT_JS)

        page.click(".castingReset")
        buttons_settle(3)
        stages["afterReset"] = page.evaluate(CASTING_REPORT_JS)

        stages["errors"] = errors
        return stages
    finally:
        context.close()


class TestTheCastingPanel:
    def test_the_limited_casting_is_listed(self, castings):
        assert castings["fresh"]["spells"] == ["dominate monster (DC 22)"]

    def test_it_is_grouped_under_how_often(self, castings):
        assert castings["fresh"]["labels"] == ["3/day"]

    def test_there_is_a_button_per_remaining_use(self, castings):
        """The buttons are the count, rather than a number written beside
        one -- the same idea the player's spell slots use."""
        assert castings["fresh"]["buttons"] == 3

    def test_the_at_will_spells_are_not_here(self, castings):
        """An Aboleth has seven of them, and none needs a counter."""
        assert "hypnotic pattern" not in " ".join(castings["fresh"]["spells"])


class TestSpendingACasting:
    def test_casting_takes_a_button_away(self, castings):
        assert castings["afterOne"]["buttons"] == 2

    def test_it_says_what_was_cast(self, castings):
        assert "dominate monster" in castings["afterOne"]["chat"]
        assert "2 left" in castings["afterOne"]["chat"]

    def test_spending_them_all_leaves_the_row_showing(self, castings):
        """Greyed rather than gone, so it is clear the creature has it and has
        used it up."""
        assert castings["spent"]["buttons"] == 0
        assert castings["spent"]["spent"] == 1
        assert castings["spent"]["spells"] == ["dominate monster (DC 22)"]

    def test_the_players_are_not_told(self, castings):
        assert "dominate monster" not in castings["playerChat"]

    def test_the_count_survives_a_reload(self, castings):
        """It lives on the server for this reason."""
        assert castings["afterReload"]["buttons"] == 0
        assert castings["afterReload"]["spent"] == 1

    def test_resetting_gives_them_back(self, castings):
        assert castings["afterReset"]["buttons"] == 3
        assert castings["afterReset"]["spent"] == 0

    def test_nothing_raised(self, castings):
        assert castings["errors"] == []


STATBLOCK_PANEL_JS = """() => {
  const panel = document.getElementById("unitStatblock");
  const named = panel.querySelector(".sbName");
  const empty = panel.querySelector(".statblockEmpty");
  return {
    name: named ? named.innerText : "",
    empty: empty ? empty.innerText : "",
    hasBlock: panel.querySelector(".statblock") !== null,
    text: panel.innerText,
    sheetName: document.getElementById("charactername").innerText,
    unitsTab: document.getElementById("units").style.display,
    scrolls: getComputedStyle(panel).overflowY,
  };
}"""


PALETTE_REPORT_JS = """() => {
  const bar = document.getElementById("mapTools").getBoundingClientRect();
  const groups = Array.from(document.querySelectorAll(".toolGroup"))
      .filter(g => g.getBoundingClientRect().width > 0);
  return {
    labels: groups.map(g => g.querySelector(".toolGroupLabel").innerText),
    barBottom: Math.round(bar.bottom),
    viewport: window.innerHeight,
    bottoms: groups.map(g => Math.round(g.getBoundingClientRect().bottom)),
    rows: new Set(groups.map(g => Math.round(g.getBoundingClientRect().top))).size,
    switches: Array.from(document.querySelectorAll(".toolToggle input"))
        .map(i => Math.round(i.getBoundingClientRect().bottom)),
  };
}"""


@pytest.fixture(scope="module")
def unit_statblock(browser, live_server):
    """Reach a monster's bestiary entry from the encounter, four ways.

    The GM could see the full entry while choosing a creature and never again;
    once it was on the board the only way back to its special abilities was to
    search the picker for it a second time.
    """
    context = browser.new_context(viewport={"width": 1500, "height": 1000})
    try:
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(live_server + "/")
        page.wait_for_function(
            "() => typeof socket !== 'undefined' && socket !== null && socket.connected",
            timeout=HANDSHAKE_TIMEOUT,
        )
        page.fill("#gameName", "statblocks")
        page.click("text=Create Game")
        page.wait_for_url("**/gm.html*", timeout=HANDSHAKE_TIMEOUT)
        page.wait_for_selector("#mapForm", state="attached")
        room = dict(pair.split("=", 1) for pair in page.url.split("?", 1)[1].split("&"))["room"]

        page.fill("#mapWidth", "5")
        page.fill("#mapHeight", "4")
        page.click("text=Generate Map")
        page.wait_for_function(
            "() => document.querySelectorAll('#mapGraphic .mapTile').length === 20",
            timeout=HANDSHAKE_TIMEOUT,
        )

        # A player, so there is a unit that never came out of the bestiary.
        player = context.new_page()
        player.goto("%s/player.html?room=%s&charName=Aria" % (live_server, room))
        player.wait_for_function(
            "() => typeof socket !== 'undefined' && socket !== null && socket.connected",
            timeout=HANDSHAKE_TIMEOUT,
        )
        page.wait_for_function(
            """() => gmData && gmData.unitList.some(u => u.charName === "Aria")""",
            timeout=HANDSHAKE_TIMEOUT,
        )

        page.click("div.tab:text-is('Encounter')")
        page.check("#addToInit")
        page.click("#chooseMonsterButton")
        page.wait_for_selector("#creatureSearchName")
        page.fill("#creatureSearchName", "dire ape")
        page.wait_for_function(
            "() => document.querySelectorAll('#creatureRows tr').length > 0",
            timeout=HANDSHAKE_TIMEOUT,
        )
        page.click("#creatureRows tr:first-child button")
        page.wait_for_function(
            "() => !document.getElementById('modalBackground')", timeout=HANDSHAKE_TIMEOUT)
        page.click("text=Add Unit")
        page.wait_for_function(
            """() => gmData && gmData.unitList.some(u => u.charName === "Dire Ape")""",
            timeout=HANDSHAKE_TIMEOUT,
        )
        page.wait_for_timeout(500)

        def sheet_ready(name):
            page.wait_for_function(
                """(who) => document.getElementById("charactername").innerText === who
                     && document.getElementById("unitStatblock").firstChild !== null""",
                arg=name, timeout=HANDSHAKE_TIMEOUT)

        stages = {}

        # 1. The sheet itself.
        page.click("div.tab:text-is('Units')")
        page.evaluate("""() => populateEditChar(gmData,
            gmData.unitList.find(u => u.charName === "Dire Ape").unitNum)""")
        sheet_ready("Dire Ape")
        stages["sheet"] = page.evaluate(STATBLOCK_PANEL_JS)

        # A player's own character has no bestiary entry behind it, and the
        # panel has to say so rather than keep showing the last monster.
        page.evaluate("""() => populateEditChar(gmData,
            gmData.unitList.find(u => u.charName === "Aria").unitNum)""")
        sheet_ready("Aria")
        stages["player"] = page.evaluate(STATBLOCK_PANEL_JS)

        # 2. The Info button on the All Creatures list, from another tab.
        page.click("div.tab:text-is('Encounter')")
        page.wait_for_function(
            """() => document.getElementById("units").style.display === "none" """,
            timeout=HANDSHAKE_TIMEOUT)
        page.click("#unitsDiv .unitListEntry:has-text('Dire Ape') button:text-is('Info')")
        sheet_ready("Dire Ape")
        stages["fromList"] = page.evaluate(STATBLOCK_PANEL_JS)
        stages["listSelected"] = page.evaluate("() => selectedUnits.slice()")
        # Where it landed, not merely whether it is displayed. The first cut of
        # this put the panel under the whole form, where it opened six pixels
        # below the fold and every assertion here still passed.
        stages["box"] = page.evaluate("""() => {
            const r = document.getElementById("unitStatblock").getBoundingClientRect();
            return {top: r.top, left: r.left, right: r.right, bottom: r.bottom,
                    vw: window.innerWidth, vh: window.innerHeight,
                    sideways: document.documentElement.scrollWidth > window.innerWidth};
        }""")

        # 3. The Info button in the initiative order, which is what the GM is
        #    actually looking at during a fight.
        page.evaluate("""() => populateEditChar(gmData,
            gmData.unitList.find(u => u.charName === "Aria").unitNum)""")
        sheet_ready("Aria")
        page.click("div.tab:text-is('Encounter')")
        page.click("#initiativeDiv .InitEntry:has-text('Dire Ape') button:text-is('Info')")
        sheet_ready("Dire Ape")
        stages["fromInitiative"] = page.evaluate(STATBLOCK_PANEL_JS)

        # 4. The token on the map. Put the ape on a tile first.
        page.evaluate("""() => populateEditChar(gmData,
            gmData.unitList.find(u => u.charName === "Aria").unitNum)""")
        page.click("div.tab:text-is('Encounter')")
        # Info left the ape selected and clicking its row is a toggle, so
        # without this the click would deselect it and the square do nothing.
        page.evaluate("() => deselectAll()")
        page.click("#unitsDiv .unitListEntry:has-text('Dire Ape')")
        # Opening any tab collapses the map to nothing, so it has to come back
        # before a square can be clicked.
        page.click("div.tab:text-is('Map')")
        page.click('[id="tile2,2"]')
        page.wait_for_function(
            """() => document.getElementById("tile2,2").attributes.units !== "" """,
            timeout=HANDSHAKE_TIMEOUT)
        page.evaluate("""() => populateEditChar(gmData,
            gmData.unitList.find(u => u.charName === "Aria").unitNum)""")
        sheet_ready("Aria")
        page.dblclick('[id="tile2,2"]')
        sheet_ready("Dire Ape")
        stages["fromMap"] = page.evaluate(STATBLOCK_PANEL_JS)

        # The panel is redrawn on every update from the server. Repainting an
        # unchanged entry would flicker and lose the GM's place in it, so this
        # counts what the sheet actually asks the server for.
        page.evaluate("""() => {
            window.creatureFetches = 0;
            const real = window.fetchCreature;
            window.fetchCreature = function (id) {
                window.creatureFetches += 1;
                return real(id);
            };
        }""")
        page.evaluate(
            """() => { window.blockNode = document.getElementById("unitStatblock").firstChild; }""")
        page.evaluate("""() => {
            for (var n = 0; n < 5; n++) {
                populateEditChar(gmData,
                    gmData.unitList.find(u => u.charName === "Dire Ape").unitNum);
            }
        }""")
        page.wait_for_timeout(400)
        stages["refetches"] = page.evaluate("() => window.creatureFetches")
        # The cache alone would still tear the panel down and build it again on
        # every update. This is the same node or it is not.
        stages["sameNode"] = page.evaluate(
            """() => document.getElementById("unitStatblock").firstChild === window.blockNode""")
        stages["stillDrawn"] = page.evaluate(STATBLOCK_PANEL_JS)

        # The players' own sheet has no such panel, and drawing must not throw
        # in a page that does not have one.
        player.wait_for_timeout(300)
        stages["playerHasPanel"] = player.evaluate(
            "() => document.getElementById('unitStatblock') !== null")
        stages["playerErrors"] = player.evaluate(
            "() => document.getElementById('chatText').innerText")

        # The statblock is floated, and a block box does not avoid a float --
        # only its line boxes do. Without a formatting context of their own the
        # attack and casting rows run in behind it.
        page.evaluate("""() => populateEditChar(gmData,
            gmData.unitList.find(u => u.charName === "Dire Ape").unitNum)""")
        page.wait_for_timeout(400)
        stages["overlap"] = page.evaluate("""() => {
            const sb = document.getElementById("unitStatblock").getBoundingClientRect();
            const bad = [];
            for (const sel of ["#unitAttacks *", "#unitCastings *",
                               "#units .sectionHeading"]) {
                for (const e of document.querySelectorAll(sel)) {
                    const r = e.getBoundingClientRect();
                    if (r.width > 0 && r.right > sb.left + 1
                        && r.top < sb.bottom && r.bottom > sb.top) {
                        bad.push(e.tagName + "." + e.className);
                    }
                }
            }
            return bad;
        }""")

        stages["errors"] = errors
        return stages
    finally:
        context.close()


class TestTheStatblockOnTheUnitSheet:
    def test_nothing_runs_in_behind_the_statblock(self, unit_statblock):
        """The fields sit beside it, not under it."""
        assert unit_statblock["overlap"] == []

    def test_a_monster_shows_its_bestiary_entry(self, unit_statblock):
        assert unit_statblock["sheet"]["hasBlock"]
        assert unit_statblock["sheet"]["name"] == "Dire Ape"

    def test_it_carries_what_the_unit_does_not(self, unit_statblock):
        """The point of the panel. A Unit keeps only the fields the app reads,
        so the feats and the prose exist nowhere but the database."""
        assert "Iron Will" in unit_statblock["sheet"]["text"]
        assert "stymied" in unit_statblock["sheet"]["text"]

    def test_a_hand_made_unit_says_so(self, unit_statblock):
        assert not unit_statblock["player"]["hasBlock"]
        assert "bestiary" in unit_statblock["player"]["empty"]

    def test_the_panel_scrolls(self, unit_statblock):
        """A dragon's entry is longer than the sheet above it, and the fields
        have to stay reachable."""
        assert unit_statblock["sheet"]["scrolls"] == "auto"


class TestReachingTheStatblock:
    def test_the_creature_list_has_an_info_button(self, unit_statblock):
        assert unit_statblock["fromList"]["name"] == "Dire Ape"
        assert unit_statblock["fromList"]["unitsTab"] == "block"

    def test_the_info_button_also_selects_the_unit(self, unit_statblock):
        """It stops the row's own click, so it has to do the selecting itself
        or the GM loses the unit they were moving."""
        assert unit_statblock["listSelected"] != []

    def test_it_opens_where_the_gm_can_see_it(self, unit_statblock):
        """Being in the document is not the same as being on the screen, and
        the difference does not show up in any of the assertions above."""
        box = unit_statblock["box"]
        assert box["top"] >= 0 and box["bottom"] <= box["vh"]
        assert box["left"] >= 0 and box["right"] <= box["vw"]
        assert box["sideways"] is False

    def test_the_initiative_order_has_one_too(self, unit_statblock):
        assert unit_statblock["fromInitiative"]["name"] == "Dire Ape"
        assert unit_statblock["fromInitiative"]["unitsTab"] == "block"

    def test_double_clicking_the_token_opens_it(self, unit_statblock):
        """Single click is already select-and-move, so this needs its own
        gesture."""
        assert unit_statblock["fromMap"]["name"] == "Dire Ape"
        assert unit_statblock["fromMap"]["unitsTab"] == "block"


class TestTheStatblockIsNotRedrawn:
    def test_the_creature_is_only_asked_for_once(self, unit_statblock):
        """populateEditChar runs on every update from the server, including
        while the tab is shut."""
        assert unit_statblock["refetches"] == 0

    def test_an_unchanged_entry_is_left_where_it_is(self, unit_statblock):
        """Rebuilding it would flicker and throw away wherever the GM had
        scrolled to in a long entry."""
        assert unit_statblock["sameNode"] is True

    def test_and_stays_on_screen(self, unit_statblock):
        assert unit_statblock["stillDrawn"]["name"] == "Dire Ape"

    def test_the_players_sheet_has_no_panel(self, unit_statblock):
        assert unit_statblock["playerHasPanel"] is False

    def test_nothing_raised(self, unit_statblock):
        assert unit_statblock["errors"] == []


@pytest.fixture(scope="module")
def chrome(browser, live_server):
    """The app's own chrome: the tab bar, and things fitting inside things.

    Both of the checks here are for defects that a green suite happily agreed
    with. A one-pixel border on the tab bar pushed the map out of the window and
    broke the battlemap drag; the attack row's number fields ignored their
    flex-basis and ran off the end of the card they sit in.
    """
    context = browser.new_context(viewport={"width": 1500, "height": 1000})
    try:
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(live_server + "/")
        page.wait_for_function(
            "() => typeof socket !== 'undefined' && socket !== null && socket.connected",
            timeout=HANDSHAKE_TIMEOUT,
        )
        page.fill("#gameName", "chrome")
        page.click("text=Create Game")
        page.wait_for_url("**/gm.html*", timeout=HANDSHAKE_TIMEOUT)
        page.wait_for_selector("#mapForm", state="attached")

        stages = {}
        GAPS_JS = """() => {
            const c = document.getElementById("mapContainer");
            const box = c.getBoundingClientRect();
            const tiles = document.querySelectorAll("#mapGraphic .mapTile");
            let left = Infinity, top = Infinity, right = -Infinity, bottom = -Infinity;
            for (const t of tiles) {
                const r = t.getBoundingClientRect();
                left = Math.min(left, r.left); top = Math.min(top, r.top);
                right = Math.max(right, r.right); bottom = Math.max(bottom, r.bottom);
            }
            return {left: Math.round(left - box.left), top: Math.round(top - box.top),
                    right: Math.round(box.right - right),
                    bottom: Math.round(box.bottom - bottom)};
        }"""

        # A map bigger than the box it sits in, so it genuinely scrolls, and
        # the sheet has to show on the far side of the grid as well as before
        # it.
        page.fill("#mapWidth", "22")
        page.fill("#mapHeight", "18")
        page.click("text=Generate Map")
        page.wait_for_function(
            "() => document.querySelectorAll('#mapGraphic .mapTile').length === 396",
            timeout=HANDSHAKE_TIMEOUT,
        )
        page.wait_for_timeout(400)
        stages["insetStart"] = page.evaluate(GAPS_JS)
        page.evaluate("""() => { const c = document.getElementById("mapContainer");
            c.scrollLeft = c.scrollWidth; c.scrollTop = c.scrollHeight; }""")
        page.wait_for_timeout(350)
        stages["insetCorner"] = page.evaluate(GAPS_JS)

        measure = """() => {
            const bar = document.querySelector(".tabsDiv").getBoundingClientRect();
            const centre = document.querySelector(".centerDiv").getBoundingClientRect();
            return {barHeight: Math.round(bar.height),
                    centreBottom: Math.round(centre.bottom),
                    viewport: window.innerHeight,
                    sideways: document.documentElement.scrollWidth > window.innerWidth,
                    overhang: document.documentElement.scrollHeight - window.innerHeight};
        }"""
        stages["layout"] = page.evaluate(measure)

        active = """() => {
            const on = Array.from(document.querySelectorAll(".tab.tabActive"));
            return on.map(t => t.innerText.trim());
        }"""
        stages["openedOn"] = page.evaluate(active)
        page.click("div.tab:text-is('Encounter')")
        stages["afterClick"] = page.evaluate(active)
        page.click("div.tab:text-is('Map')")
        stages["backToMap"] = page.evaluate(active)

        # A creature with four attacks, to measure the row against its card.
        page.click("div.tab:text-is('Encounter')")
        page.click("#chooseMonsterButton")
        page.wait_for_selector("#creatureSearchName")
        page.fill("#creatureSearchName", "adult occult dragon")
        page.wait_for_function(
            "() => document.querySelectorAll('#creatureRows tr').length > 0",
            timeout=HANDSHAKE_TIMEOUT,
        )
        page.click("#creatureRows tr:first-child button")
        page.wait_for_function(
            "() => !document.getElementById('modalBackground')", timeout=HANDSHAKE_TIMEOUT)
        page.click("text=Add Unit")
        page.wait_for_function(
            """() => gmData && gmData.unitList.some(u => u.charName === "Adult Occult Dragon")""",
            timeout=HANDSHAKE_TIMEOUT,
        )
        page.wait_for_timeout(400)
        page.click("div.tab:text-is('Units')")
        page.evaluate("""() => populateEditChar(gmData,
            gmData.unitList.find(u => u.charName === "Adult Occult Dragon").unitNum)""")
        page.wait_for_function(
            "() => document.querySelectorAll('#unitAttacks .attackRow').length > 0",
            timeout=HANDSHAKE_TIMEOUT,
        )
        stages["attacks"] = page.evaluate("""() => {
            const card = document.querySelector("#units .formCard").getBoundingClientRect();
            const rows = Array.from(document.querySelectorAll("#unitAttacks .attackRow"));
            const widest = Math.max(...rows.map(r => {
                const kids = Array.from(r.children);
                return Math.max(...kids.map(k => k.getBoundingClientRect().right));
            }));
            return {cardRight: Math.round(card.right), widestChildRight: Math.round(widest),
                    fieldWidths: Array.from(rows[0].children).map(
                        k => Math.round(k.getBoundingClientRect().width))};
        }""")

        # The palette, with the movement controls showing -- which is when it is
        # at its widest, and when a floated layout pushed the switches off the
        # bottom of the window.
        page.click("div.tab:text-is('Encounter')")
        page.check("#addToInit")
        page.fill("#unitName", "Goblin")
        page.fill("#unitHP", "6")
        page.fill("#unitInit", "12")
        page.click("text=Add Unit")
        page.wait_for_timeout(400)
        page.click("div.tab:text-is('Map')")
        page.click("#beginInit")
        page.wait_for_function(
            """() => getComputedStyle(
                 document.getElementById("movementDiv")).display !== "none" """,
            timeout=HANDSHAKE_TIMEOUT)
        stages["palette"] = page.evaluate(PALETTE_REPORT_JS)

        # And again with the window too narrow to hold it. This is where the
        # floated version failed: it wrapped, and a wrapped bar pinned to the
        # bottom of the window is a bar with its last group off the screen.
        page.set_viewport_size({"width": 1080, "height": 820})
        page.wait_for_timeout(400)
        stages["paletteNarrow"] = page.evaluate(PALETTE_REPORT_JS)
        page.set_viewport_size({"width": 1500, "height": 1000})
        page.wait_for_timeout(300)

        stages["errors"] = errors
        return stages
    finally:
        context.close()


class TestThePalette:
    def test_the_tools_are_grouped_and_named(self, chrome):
        assert chrome["palette"]["labels"] == [
            "Terrain", "Doors & Stairs", "Markers", "Light", "Movement",
            "Map", "Show"]

    def test_every_group_is_on_one_row(self, chrome):
        """Floated, the last group wrapped to a second line as soon as the
        movement controls appeared -- and on a bar pinned to the bottom of the
        window, a second line is off the screen."""
        assert chrome["palette"]["rows"] == 1

    def test_no_group_hangs_below_the_bar(self, chrome):
        bar_bottom = chrome["palette"]["barBottom"]
        for bottom in chrome["palette"]["bottoms"]:
            assert bottom <= bar_bottom + 1, (bottom, bar_bottom)

    def test_the_switches_are_on_the_screen(self, chrome):
        """The thing that actually went wrong: they were in the document, and
        every assertion about them existing passed."""
        viewport = chrome["palette"]["viewport"]
        assert chrome["palette"]["switches"], "no switches found"
        for bottom in chrome["palette"]["switches"]:
            assert 0 < bottom <= viewport, (bottom, viewport)

    def test_it_survives_a_window_too_narrow_for_it(self, chrome):
        """The bar scrolls sideways rather than wrapping. Wrapping is what put
        the switches off the bottom of the screen."""
        narrow = chrome["paletteNarrow"]
        assert narrow["rows"] == 1
        assert narrow["labels"] == chrome["palette"]["labels"]
        for bottom in narrow["bottoms"]:
            assert bottom <= narrow["barBottom"] + 1, (bottom, narrow["barBottom"])


class TestTheTabBar:
    def test_it_keeps_to_forty_pixels(self, chrome):
        """Everything below is laid out against calc(100% - 40px), so a taller
        bar pushes the map a pixel out of the window."""
        assert chrome["layout"]["barHeight"] == 40

    def test_the_page_does_not_scroll(self, chrome):
        """Sideways never; downwards only by the fraction of a pixel the
        whitespace line box above has always cost."""
        assert chrome["layout"]["sideways"] is False
        assert chrome["layout"]["overhang"] <= 1

    def test_the_page_reaches_the_bottom_of_the_window(self, chrome):
        """Within a pixel: a whitespace text node between the bar and the page
        forms an anonymous line box, which has always cost a fraction of one."""
        assert abs(chrome["layout"]["centreBottom"] - chrome["layout"]["viewport"]) <= 1

    def test_the_map_tab_starts_marked(self, chrome):
        """Nothing on screen said which tab you were on."""
        assert chrome["openedOn"] == ["Map"]

    def test_the_mark_follows_the_click(self, chrome):
        assert chrome["afterClick"] == ["Encounter"]
        assert chrome["backToMap"] == ["Map"]


class TestThingsFitInsideThings:
    def test_the_attack_row_stays_inside_its_card(self, chrome):
        assert chrome["attacks"]["widestChildRight"] <= chrome["attacks"]["cardRight"]

    def test_the_number_fields_are_not_full_width(self, chrome):
        """A flex item defaults to min-width:auto, which for a text input is its
        twenty-character preferred size -- so flex-basis was being ignored and
        every field came out the same 205px."""
        name, bonus, damage, crit = chrome["attacks"]["fieldWidths"][:4]
        assert bonus < 100 and damage < 120 and crit < 100
        assert name > bonus

    def test_nothing_raised(self, chrome):
        assert chrome["errors"] == []


# Every string of text the eye can land on, with the colour it is drawn in and
# the colour actually behind it, as a contrast ratio. The desk went dark
# partway through the design work and took several panels with it -- the
# character sheet, the inventory, the lore pages and the player links were all
# still ink on bare page, which by then meant ink on walnut.
CONTRAST_JS = """(panelId) => {
  const luminance = (rgb) => {
    const [r, g, b] = rgb.map(v => {
      const c = v / 255;
      return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
    });
    return 0.2126 * r + 0.7152 * g + 0.0722 * b;
  };
  const parse = (s) => {
    const m = s.match(/rgba?\\(([^)]+)\\)/);
    if (!m) return null;
    const parts = m[1].split(",").map(x => parseFloat(x));
    return {rgb: parts.slice(0, 3), a: parts.length > 3 ? parts[3] : 1};
  };
  // What is actually behind an element: the first ancestor that paints.
  const ground = (el) => {
    let e = el;
    while (e && e !== document.documentElement) {
      const cs = getComputedStyle(e);
      const bg = parse(cs.backgroundColor);
      if (bg && bg.a > 0.5) return bg.rgb;
      if (cs.backgroundImage !== "none") return null;  // artwork, not chrome
      e = e.parentElement;
    }
    const body = parse(getComputedStyle(document.body).backgroundColor);
    return body ? body.rgb : [255, 255, 255];
  };
  const panel = document.getElementById(panelId);
  const bad = [];
  const seen = new Set();
  for (const el of panel.querySelectorAll("*")) {
    if (el.offsetParent === null) continue;
    const box = el.getBoundingClientRect();
    if (box.width < 4 || box.height < 4) continue;
    const own = Array.from(el.childNodes)
        .filter(n => n.nodeType === 3).map(n => n.textContent.trim()).join("");
    if (own.length < 2) continue;
    const cs = getComputedStyle(el);
    if (cs.visibility === "hidden" || parseFloat(cs.opacity) < 0.3) continue;
    const fg = parse(cs.color);
    const bg = ground(el);
    if (!fg || !bg) continue;
    const a = luminance(fg.rgb), b = luminance(bg);
    const ratio = (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
    const key = own.slice(0, 24);
    if (ratio < 3 && !seen.has(key)) {
      seen.add(key);
      bad.push({text: key, ratio: Math.round(ratio * 100) / 100,
                colour: cs.color, ground: "rgb(" + bg.join(",") + ")"});
    }
  }
  return bad;
}"""


@pytest.fixture(scope="module")
def legibility(browser, live_server):
    """Walk every tab on both views and measure the text against its ground."""
    context = browser.new_context(viewport={"width": 1500, "height": 1000})
    try:
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(live_server + "/")
        page.wait_for_function(
            "() => typeof socket !== 'undefined' && socket !== null && socket.connected",
            timeout=HANDSHAKE_TIMEOUT,
        )
        page.fill("#gameName", "legibility")
        page.click("text=Create Game")
        page.wait_for_url("**/gm.html*", timeout=HANDSHAKE_TIMEOUT)
        page.wait_for_selector("#mapForm", state="attached")
        room = dict(pair.split("=", 1) for pair in page.url.split("?", 1)[1].split("&"))["room"]

        player = context.new_page()
        player.goto("%s/player.html?room=%s&charName=Aria" % (live_server, room))
        player.wait_for_function(
            "() => typeof socket !== 'undefined' && socket !== null && socket.connected",
            timeout=HANDSHAKE_TIMEOUT,
        )
        page.wait_for_function(
            """() => gmData && gmData.unitList.some(u => u.charName === "Aria")""",
            timeout=HANDSHAKE_TIMEOUT,
        )
        player.wait_for_timeout(700)

        # Where each sheet sits, as well as what it says. An id beats a class,
        # so a leftover height:100% on a panel overrode the sheet's own sizing
        # and ran it past its holder, over the scrollbar.
        FITS_JS = """(panelId) => {
          const p = document.getElementById(panelId).getBoundingClientRect();
          const h = document.getElementById("activeTabDiv").getBoundingClientRect();
          return {panel: [Math.round(p.top), Math.round(p.bottom),
                          Math.round(p.left), Math.round(p.right)],
                  holder: [Math.round(h.top), Math.round(h.bottom),
                           Math.round(h.left), Math.round(h.right)],
                  viewport: window.innerHeight};
        }"""

        found = {}
        fits = {}
        for tab, panel in [("Encounter", "encounterContainer"), ("Save", "saveGame"),
                           ("Players", "links"), ("Units", "units"),
                           ("Lore", "lore"), ("Rules", "rules"),
                           ("Options", "options")]:
            page.click("div.tab:text-is('%s')" % tab)
            page.wait_for_timeout(350)
            found["gm " + tab] = page.evaluate(CONTRAST_JS, panel)
            fits["gm " + tab] = page.evaluate(FITS_JS, panel)
        page.click("div.tab:text-is('Map')")
        page.wait_for_timeout(300)
        found["gm palette"] = page.evaluate(CONTRAST_JS, "mapTools")

        for tab, panel in [("Character", "charWrapper"), ("Inventory", "inventory"),
                           ("Lore", "lore")]:
            player.click("div.tab:text-is('%s')" % tab)
            player.wait_for_timeout(400)
            found["player " + tab] = player.evaluate(CONTRAST_JS, panel)
            fits["player " + tab] = player.evaluate(FITS_JS, panel)

        return {"found": found, "fits": fits, "errors": errors}
    finally:
        context.close()


class TestEveryTabIsLegible:
    def test_nothing_is_ink_on_walnut(self, legibility):
        """A contrast ratio under 3 against whatever is actually behind it.

        This is the check that would have caught the character sheet, the
        inventory, the lore pages and the player links all at once -- every one
        of them was in the document, laid out correctly, and unreadable.
        """
        offenders = {k: v for k, v in legibility["found"].items() if v}
        assert offenders == {}

    def test_no_panel_runs_past_its_holder(self, legibility):
        """An id beats a class: a leftover height:100% on #lore overrode the
        sheet's calc(100% - 16px) and drew the box over the scrollbar."""
        over = {}
        for name, box in legibility["fits"].items():
            top, bottom, left, right = box["panel"]
            htop, hbottom, hleft, hright = box["holder"]
            if bottom > hbottom or top < htop or right > hright or left < hleft:
                over[name] = box
        assert over == {}

    def test_no_panel_runs_off_the_window(self, legibility):
        for name, box in legibility["fits"].items():
            assert box["panel"][1] <= box["viewport"], (name, box)

    def test_nothing_raised(self, legibility):
        assert legibility["errors"] == []


@pytest.fixture(scope="module")
def scrollbars(browser, live_server):
    """Whether the page shell overflows, at several window sizes.

    A single pixel of overflow puts a scrollbar down the right-hand edge, and
    the tab panels run the full width of the window -- so the scrollbar lands
    on top of one. Headless Chromium draws overlay scrollbars, which take no
    width, so nothing measured as covered and the assertions all passed while
    the panel sat under a real scrollbar in a real browser. Measuring the
    overflow itself is the check that works either way.
    """
    context = browser.new_context(viewport={"width": 1500, "height": 1000})
    try:
        page = context.new_page()
        page.goto(live_server + "/")
        page.wait_for_function(
            "() => typeof socket !== 'undefined' && socket !== null && socket.connected",
            timeout=HANDSHAKE_TIMEOUT,
        )
        page.fill("#gameName", "scrollbars")
        page.click("text=Create Game")
        page.wait_for_url("**/gm.html*", timeout=HANDSHAKE_TIMEOUT)
        page.wait_for_selector("#mapForm", state="attached")
        room = dict(pair.split("=", 1) for pair in page.url.split("?", 1)[1].split("&"))["room"]

        player = context.new_page()
        player.goto("%s/player.html?room=%s&charName=Aria" % (live_server, room))
        player.wait_for_function(
            "() => typeof socket !== 'undefined' && socket !== null && socket.connected",
            timeout=HANDSHAKE_TIMEOUT,
        )
        player.wait_for_timeout(600)

        probe = """() => {
            const sd = document.getElementById("screenDiv");
            return {overflowDown: sd.scrollHeight - sd.clientHeight,
                    overflowAcross: sd.scrollWidth - sd.clientWidth,
                    overflowStyle: getComputedStyle(sd).overflow};
        }"""
        sizes = {}
        for width, height in [(1500, 1000), (1366, 768), (1920, 1080), (1280, 720)]:
            page.set_viewport_size({"width": width, "height": height})
            player.set_viewport_size({"width": width, "height": height})
            page.wait_for_timeout(250)
            player.wait_for_timeout(250)
            sizes["gm %dx%d" % (width, height)] = page.evaluate(probe)
            sizes["player %dx%d" % (width, height)] = player.evaluate(probe)
        return sizes
    finally:
        context.close()


class TestThePageDoesNotOverflow:
    def test_the_shell_never_scrolls(self, scrollbars):
        """One pixel is all it takes to put a scrollbar over a tab panel."""
        over = {k: v for k, v in scrollbars.items()
                if v["overflowDown"] > 0 or v["overflowAcross"] > 0}
        assert over == {}

    def test_and_could_not_show_a_scrollbar_if_it_did(self, scrollbars):
        """Belt and braces: the shell clips rather than scrolls, so no
        scrollbar can appear on it whatever the content does."""
        for name, box in scrollbars.items():
            assert box["overflowStyle"] == "hidden", (name, box)


class TestTheMapSitsInsideItsSheet:
    def test_the_sheet_shows_before_the_grid(self, chrome):
        assert chrome["insetStart"]["left"] > 0
        assert chrome["insetStart"]["top"] > 0

    def test_and_after_it_when_scrolled_to_the_far_corner(self, chrome):
        """These two are the ones that need #mapGraphic to have a size of its
        own: every tile in it is absolutely positioned, so without one the
        scroll extent stops at the last tile."""
        assert chrome["insetCorner"]["right"] > 0
        assert chrome["insetCorner"]["bottom"] > 0

    def test_the_inset_is_the_same_all_round(self, chrome):
        assert chrome["insetStart"]["left"] == chrome["insetStart"]["top"]
        assert chrome["insetCorner"]["right"] == chrome["insetCorner"]["bottom"]
        assert chrome["insetStart"]["left"] == chrome["insetCorner"]["right"]


@pytest.fixture(scope="module")
def creature_panel(browser, live_server):
    """The GM's creature panel under the map: the one the players' action bar
    is in the same place as.

    It shows whatever the GM has selected, and failing that whoever's turn it
    is, so the states worth measuring are: shut, open with nothing to show,
    open on a selected creature, and open on the current turn with nothing
    selected.
    """
    context = browser.new_context(viewport={"width": 1500, "height": 1000})
    try:
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(live_server + "/")
        page.wait_for_function(
            "() => typeof socket !== 'undefined' && socket !== null && socket.connected",
            timeout=HANDSHAKE_TIMEOUT,
        )
        page.fill("#gameName", "creature panel")
        page.click("text=Create Game")
        page.wait_for_url("**/gm.html*", timeout=HANDSHAKE_TIMEOUT)
        page.wait_for_selector("#mapForm", state="attached")

        page.fill("#mapWidth", "14")
        page.fill("#mapHeight", "10")
        page.click("text=Generate Map")
        page.wait_for_function(
            "() => document.querySelectorAll('#mapGraphic .mapTile').length === 140",
            timeout=HANDSHAKE_TIMEOUT,
        )
        page.wait_for_timeout(400)

        REPORT = """() => {
            const panel = document.getElementById("bottomDiv");
            const box = panel.getBoundingClientRect();
            const sheet = document.getElementById("mapWrapper").getBoundingClientRect();
            return {
                shown: getComputedStyle(panel).display !== "none",
                name: document.getElementById("mobPanelName").innerText.trim(),
                stats: Array.from(document.querySelectorAll("#mobPanelStats .mobStat"))
                            .map(s => s.innerText.replace(/\\s+/g, " ").trim()),
                attacks: document.querySelectorAll("#mobPanelAttacks .attackRow").length,
                castingRows: document.querySelectorAll("#mobPanelCastings .castingRow").length,
                panelTop: Math.round(box.top),
                panelBottom: Math.round(box.bottom),
                sheetBottom: Math.round(sheet.bottom),
                viewport: window.innerHeight,
            };
        }"""
        # The palette lives inside the map sheet, and the sheet gets shorter
        # when the panel opens.
        PALETTE_FIT = """() => {
            const bar = document.getElementById("mapTools");
            const groups = Array.from(document.querySelectorAll(".toolGroup"))
                .filter(g => g.getBoundingClientRect().height > 0);
            return {
                barHeight: Math.round(bar.getBoundingClientRect().height),
                tallestGroup: Math.max(...groups.map(g => g.scrollHeight)),
            };
        }"""

        stages = {}
        stages["shut"] = page.evaluate(REPORT)
        # Straight off a freshly loaded page: the tab's two functions hand the
        # click back and forth to each other, so if neither has run on load the
        # tab is dead until something else happens to call one.
        page.click("#bottomPopupButton")
        page.wait_for_timeout(400)
        stages["openedFromFreshPage"] = page.evaluate(REPORT)
        stages["paletteWithPanelOpen"] = page.evaluate(PALETTE_FIT)

        # A creature with attacks and spells that run out.
        page.click("div.tab:text-is('Encounter')")
        page.click("#chooseMonsterButton")
        page.wait_for_selector("#creatureSearchName")
        page.fill("#creatureSearchName", "adult occult dragon")
        page.wait_for_function(
            "() => document.querySelectorAll('#creatureRows tr').length > 0",
            timeout=HANDSHAKE_TIMEOUT,
        )
        page.click("#creatureRows tr:first-child button")
        page.wait_for_function(
            "() => !document.getElementById('modalBackground')", timeout=HANDSHAKE_TIMEOUT)
        page.check("#addToInit")
        page.fill("#unitInit", "17")
        page.click("text=Add Unit")
        page.wait_for_function(
            """() => gmData && gmData.unitList.some(u => u.charName === "Adult Occult Dragon")""",
            timeout=HANDSHAKE_TIMEOUT,
        )
        page.wait_for_timeout(400)

        # Selecting it from the unit list. Changing tabs shuts the panel -- it
        # is anchored under the map -- so it is opened again after coming back.
        page.click("div.tab:text-is('Units')")
        page.click("#unitsDiv .unitListEntry")
        page.wait_for_timeout(600)
        page.click("div.tab:text-is('Map')")
        stages["shutByChangingTabs"] = page.evaluate(REPORT)
        page.click("#bottomPopupButton")
        page.wait_for_timeout(700)
        stages["selected"] = page.evaluate(REPORT)

        # In initiative with nothing selected, it follows whose turn it is.
        page.click("#beginInit")
        page.wait_for_function(
            """() => getComputedStyle(
                 document.getElementById("movementDiv")).display !== "none" """,
            timeout=HANDSHAKE_TIMEOUT)
        page.evaluate("() => deselectAll()")
        page.wait_for_timeout(600)
        stages["currentTurn"] = page.evaluate(REPORT)

        # The abilities, folded away behind the button in the heading.
        ABILITIES = """() => {
            const ab = document.getElementById("mobPanelAbilities");
            const btn = document.getElementById("mobPanelAbilitiesButton");
            const showing = getComputedStyle(ab).display !== "none";
            const box = ab.getBoundingClientRect();
            const cols = document.querySelector(".mobPanelColumns").getBoundingClientRect();
            const stats = document.getElementById("mobPanelStats").getBoundingClientRect();
            return {
                showing: showing,
                buttonDisabled: btn.disabled,
                buttonTitle: btn.title,
                entries: ab.querySelectorAll(".sbAbilityEntry").length,
                boldLeads: ab.querySelectorAll(".sbAbilityEntry b").length,
                statsStillVisible: stats.height > 0,
                coversTheColumns: showing
                    ? Math.round(box.top) <= Math.round(cols.top) + 1
                      && Math.round(box.bottom) >= Math.round(cols.bottom) - 1 : null,
                clearsTheStatStrip: showing
                    ? Math.round(box.top) >= Math.round(stats.bottom) - 1 : null,
            };
        }"""
        stages["abilitiesFolded"] = page.evaluate(ABILITIES)
        page.click("#mobPanelAbilitiesButton")
        page.wait_for_timeout(400)
        stages["abilitiesOpen"] = page.evaluate(ABILITIES)
        page.click("#mobPanelAbilitiesButton")
        page.wait_for_timeout(300)
        stages["abilitiesFoldedAgain"] = page.evaluate(ABILITIES)

        # Left open, then the panel changes creature: the last one's abilities
        # must not stay lying over the new one's attacks.
        page.click("#mobPanelAbilitiesButton")
        page.wait_for_timeout(300)
        page.click("div.tab:text-is('Encounter')")
        page.fill("#unitName", "Bandit")
        page.fill("#unitHP", "9")
        page.click("text=Add Unit")
        page.wait_for_function(
            """() => gmData && gmData.unitList.some(u => u.charName === "Bandit")""",
            timeout=HANDSHAKE_TIMEOUT,
        )
        page.wait_for_timeout(400)
        page.evaluate(
            """() => { selectedUnits =
                 [gmData.unitList.find(u => u.charName === "Bandit").unitNum];
               drawMobPanel(gmData); }""")
        page.wait_for_timeout(600)
        page.click("div.tab:text-is('Map')")
        page.click("#bottomPopupButton")
        page.wait_for_timeout(700)
        stages["handMadeUnit"] = page.evaluate(ABILITIES)
        stages["handMadeName"] = page.evaluate(
            "() => document.getElementById('mobPanelName').innerText.trim()")

        # Back to the dragon for the effect-placer checks below.
        page.evaluate(
            """() => { selectedUnits =
                 [gmData.unitList.find(u => u.charName === "Adult Occult Dragon").unitNum];
               drawMobPanel(gmData); }""")
        page.wait_for_timeout(500)

        # The effect placer borrows the same panel. It used to write a height
        # straight onto the tab holder, which outranked the class the tab uses
        # and left the panel unable to make room for itself afterwards.
        page.click("#showEffectDivButton")
        page.wait_for_timeout(400)
        stages["effectTableInItsHolder"] = page.evaluate(
            "() => !!document.querySelector('#bottomEffectHolder #effectTable')")
        stages["inlineHeightWhileEffecting"] = page.evaluate(
            "() => document.getElementById('activeTabDiv').style.height")
        page.click("#showEffectDivButton")
        page.wait_for_timeout(300)
        page.click("#bottomPopupButton")
        page.wait_for_timeout(600)
        stages["reopenedAfterEffects"] = page.evaluate(REPORT)

        stages["errors"] = errors
        return stages
    finally:
        context.close()


class TestTheCreaturePanelOpens:
    def test_it_starts_shut(self, creature_panel):
        assert creature_panel["shut"]["shown"] is False

    def test_the_tab_opens_it_on_a_page_nothing_else_has_touched(self, creature_panel):
        """hideBottomDiv and showBottomDiv each install the other as the tab's
        handler, so until one of them runs on load the tab does nothing. The
        GM view never called either, and the tab only came alive once a tab
        change happened to call one for it."""
        assert creature_panel["openedFromFreshPage"]["shown"] is True

    def test_changing_tabs_shuts_it(self, creature_panel):
        assert creature_panel["shutByChangingTabs"]["shown"] is False

    def test_the_map_sheet_gets_out_of_its_way(self, creature_panel):
        open_state = creature_panel["selected"]
        assert open_state["sheetBottom"] <= open_state["panelTop"]

    def test_it_stays_inside_the_window(self, creature_panel):
        for stage in ("openedFromFreshPage", "selected", "currentTurn"):
            state = creature_panel[stage]
            assert state["panelBottom"] <= state["viewport"], stage

    def test_the_palette_still_fits_in_the_shortened_sheet(self, creature_panel):
        """The palette is inside the map sheet, and the sheet gets shorter to
        make room for the panel. Sized as a share of the sheet it was squashed
        under its own tools, and the last row of switches was cut off."""
        fit = creature_panel["paletteWithPanelOpen"]
        assert fit["barHeight"] >= fit["tallestGroup"]


class TestWhatTheCreaturePanelShows:
    def test_nothing_selected_and_no_initiative_says_so(self, creature_panel):
        assert creature_panel["openedFromFreshPage"]["name"] == "Nothing selected"
        assert creature_panel["openedFromFreshPage"]["attacks"] == 0

    def test_a_selected_creature_is_named(self, creature_panel):
        assert creature_panel["selected"]["name"] == "Adult Occult Dragon"

    def test_its_attacks_are_listed(self, creature_panel):
        assert creature_panel["selected"]["attacks"] == 4

    def test_and_the_spells_it_can_only_cast_so_often(self, creature_panel):
        assert creature_panel["selected"]["castingRows"] > 0

    def test_hp_ac_and_initiative_are_across_the_top(self, creature_panel):
        stats = creature_panel["selected"]["stats"]
        # HP, AC and initiative to read, then the saves to roll.
        assert len(stats) == 4
        assert stats[0].startswith("HP 138 / 138")
        # A unit carries AC only as the pieces it adds up from, so this one is
        # read from the bestiary record the creature came out of.
        assert stats[1].startswith("AC 28")
        assert stats[2].startswith("Init")
        assert stats[3].startswith("Saves")

    def test_with_nothing_selected_it_follows_whose_turn_it_is(self, creature_panel):
        assert creature_panel["currentTurn"]["name"] == "Adult Occult Dragon"
        assert creature_panel["currentTurn"]["attacks"] == 4


class TestTheCreaturePanelAndTheEffectPlacer:
    def test_the_effect_table_goes_in_its_own_holder(self, creature_panel):
        assert creature_panel["effectTableInItsHolder"] is True

    def test_it_leaves_no_written_in_height_behind(self, creature_panel):
        assert creature_panel["inlineHeightWhileEffecting"] == ""

    def test_and_the_panel_still_opens_afterwards(self, creature_panel):
        after = creature_panel["reopenedAfterEffects"]
        assert after["shown"] is True
        assert after["sheetBottom"] <= after["panelTop"]


class TestTheCreaturePanelRaisedNothing:
    def test_nothing_raised(self, creature_panel):
        assert creature_panel["errors"] == []


class TestTheSpecialAbilitiesFold:
    """The rest of the bestiary entry, behind a button in the heading.

    Everything a GM reaches for in a round is on the panel already; the
    abilities are the longest thing about a creature, so they stay folded until
    something actually uses one.
    """

    def test_they_start_folded_away(self, creature_panel):
        assert creature_panel["abilitiesFolded"]["showing"] is False

    def test_the_button_is_live_for_a_bestiary_creature(self, creature_panel):
        assert creature_panel["abilitiesFolded"]["buttonDisabled"] is False

    def test_the_button_unfolds_them(self, creature_panel):
        assert creature_panel["abilitiesOpen"]["showing"] is True
        assert creature_panel["abilitiesOpen"]["entries"] > 0

    def test_each_one_leads_with_its_name_and_tag(self, creature_panel):
        """"Aura Sight (Su) An old dragon sees..." -- the same shape the
        statblock gives them, from the same builder."""
        state = creature_panel["abilitiesOpen"]
        assert state["boldLeads"] == state["entries"]

    def test_they_lie_over_the_columns(self, creature_panel):
        assert creature_panel["abilitiesOpen"]["coversTheColumns"] is True

    def test_but_leave_hp_and_ac_on_screen(self, creature_panel):
        """The stat strip is outside the stack they are laid over, so the
        figures the GM is tracking stay put while the abilities are open."""
        assert creature_panel["abilitiesOpen"]["clearsTheStatStrip"] is True
        assert creature_panel["abilitiesOpen"]["statsStillVisible"] is True

    def test_the_button_folds_them_again(self, creature_panel):
        assert creature_panel["abilitiesFoldedAgain"]["showing"] is False

    def test_changing_creature_folds_them_away(self, creature_panel):
        """Left open, the last creature's abilities would otherwise stay lying
        over the new one's attacks."""
        assert creature_panel["handMadeName"] == "Bandit"
        assert creature_panel["handMadeUnit"]["showing"] is False

    def test_a_unit_made_by_hand_says_why_there_are_none(self, creature_panel):
        """Dead with a reason rather than absent, which would read as something
        failing to load -- the same way an unrollable attack keeps its button."""
        state = creature_panel["handMadeUnit"]
        assert state["buttonDisabled"] is True
        assert "bestiary" in state["buttonTitle"]


@pytest.fixture(scope="module")
def spell_lookup(browser, live_server):
    """Clicking a spell for its rules, on both views.

    A creature's statblock names its spells and nothing more, so the GM side
    has to find the entry from that name. The player's own spells are whole
    rows out of the same table, already in hand, so that side opens the entry
    without asking the server for anything.
    """
    context = browser.new_context(viewport={"width": 1500, "height": 1000})
    try:
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(live_server + "/")
        page.wait_for_function(
            "() => typeof socket !== 'undefined' && socket !== null && socket.connected",
            timeout=HANDSHAKE_TIMEOUT,
        )
        page.fill("#gameName", "spell lookup")
        page.click("text=Create Game")
        page.wait_for_url("**/gm.html*", timeout=HANDSHAKE_TIMEOUT)
        page.wait_for_selector("#mapForm", state="attached")
        room = dict(pair.split("=", 1)
                    for pair in page.url.split("?", 1)[1].split("&"))["room"]

        page.fill("#mapWidth", "14")
        page.fill("#mapHeight", "10")
        page.click("text=Generate Map")
        page.wait_for_function(
            "() => document.querySelectorAll('#mapGraphic .mapTile').length === 140",
            timeout=HANDSHAKE_TIMEOUT,
        )

        # A creature whose castings hold several spells to a row, with DCs and
        # a source book on them.
        page.click("div.tab:text-is('Encounter')")
        page.click("#chooseMonsterButton")
        page.wait_for_selector("#creatureSearchName")
        page.fill("#creatureSearchName", "adult occult dragon")
        page.wait_for_function(
            "() => document.querySelectorAll('#creatureRows tr').length > 0",
            timeout=HANDSHAKE_TIMEOUT,
        )
        page.click("#creatureRows tr:first-child button")
        page.wait_for_function(
            "() => !document.getElementById('modalBackground')", timeout=HANDSHAKE_TIMEOUT)
        page.click("text=Add Unit")
        page.wait_for_function(
            """() => gmData && gmData.unitList.some(u => u.charName === "Adult Occult Dragon")""",
            timeout=HANDSHAKE_TIMEOUT,
        )
        page.wait_for_timeout(400)
        page.click("div.tab:text-is('Units')")
        page.click("#unitsDiv .unitListEntry")
        page.wait_for_timeout(600)
        page.click("div.tab:text-is('Map')")
        page.click("#bottomPopupButton")
        page.wait_for_timeout(800)

        stages = {}
        stages["names"] = page.eval_on_selector_all(
            "#mobPanelCastings .spellLink", "els => els.map(e => e.innerText)")

        # The list splits on commas that are not inside brackets. Naively,
        # "dispel evil (2, DC 22)" becomes two spells, one called "DC 22)".
        stages["split"] = page.evaluate(
            """() => splitSpellList("dispel evil (2, DC 22), gaseous form")""")

        def open_spell(text):
            # showSpellInfo clears any spell already open itself; the picker's
            # #modalBackground is a different dialog and is left alone.
            page.evaluate("(name) => showSpellInfo(name)", text)
            page.wait_for_selector("#spellSheet", timeout=HANDSHAKE_TIMEOUT)
            page.wait_for_function(
                """() => {
                    const note = document.querySelector(".spellSheetNote");
                    return !note || !note.innerText.includes("Looking");
                }""", timeout=HANDSHAKE_TIMEOUT)
            return {
                "heading": page.inner_text("#spellSheet .panelHeading"),
                "body": page.inner_text("#spellSheetBody"),
                "note": (page.inner_text(".spellSheetNote")
                         if page.query_selector(".spellSheetNote") else ""),
            }

        # Clicking the name in the panel rather than calling the function.
        page.click("#mobPanelCastings .spellLink >> text=gaseous form")
        page.wait_for_selector("#spellSheet", timeout=HANDSHAKE_TIMEOUT)
        page.wait_for_function(
            "() => !document.querySelector('.spellSheetNote')", timeout=HANDSHAKE_TIMEOUT)
        stages["clicked"] = {
            "heading": page.inner_text("#spellSheet .panelHeading"),
            "body": page.inner_text("#spellSheetBody"),
        }
        page.click("#spellModal", position={"x": 5, "y": 5})
        page.wait_for_timeout(300)
        stages["closesAgain"] = page.query_selector("#spellSheet") is None

        # The name is read out of the line as it is written, brackets and all.
        stages["throughTheDC"] = open_spell("suggestion (DC 17)")
        stages["throughTheSourceBook"] = open_spell("mental barrier IIOA")
        stages["rankInFront"] = open_spell("greater dispel magic")
        stages["notASpell"] = open_spell("touch of evil")
        page.click("#spellModal", position={"x": 5, "y": 5})
        page.wait_for_timeout(200)

        # The player view: its own spells are whole rows, opened without a
        # lookup, and it has the same dialog.
        player = context.new_page()
        player.on("pageerror", lambda error: errors.append("player: " + str(error)))
        player.goto("%s/player.html?room=%s&charName=Vex" % (live_server, room))
        player.wait_for_function(
            "() => typeof socket !== 'undefined' && socket !== null && socket.connected",
            timeout=HANDSHAKE_TIMEOUT,
        )
        player.wait_for_timeout(800)
        player.evaluate("""async () => {
            const rows = await new Promise(
                resolve => socket.emit('database_spells', 'Wizard', 1, resolve));
            showSpellInfo(rows.find(s => s.name.toLowerCase() === 'magic missile'));
        }""")
        player.wait_for_selector("#spellSheet", timeout=HANDSHAKE_TIMEOUT)
        stages["playerHeading"] = player.inner_text("#spellSheet .panelHeading")
        stages["playerBody"] = player.inner_text("#spellSheetBody")

        stages["errors"] = errors
        return stages
    finally:
        context.close()


class TestSpellNamesAreClickable:
    def test_every_spell_in_a_casting_row_is_its_own_link(self, spell_lookup):
        """A row can hold several -- "gaseous form, mental barrier IIOA" -- and
        the reader wants the one they pointed at, not the line."""
        names = spell_lookup["names"]
        assert "gaseous form" in names
        assert "mental barrier IIOA" in names
        assert len(names) > 5

    def test_the_name_is_shown_as_it_is_written(self, spell_lookup):
        """The DC and the source book stay on screen -- that is how the GM
        reads the line -- and are taken off only to do the lookup."""
        assert "hideous laughter (DC 15)" in spell_lookup["names"]

    def test_the_list_splits_on_brackets_not_just_commas(self, spell_lookup):
        assert spell_lookup["split"] == ["dispel evil (2, DC 22)", "gaseous form"]


class TestOpeningASpell:
    def test_clicking_one_opens_its_entry(self, spell_lookup):
        assert spell_lookup["clicked"]["heading"] == "Gaseous Form"

    def test_the_entry_has_the_rules_in_it(self, spell_lookup):
        body = spell_lookup["clicked"]["body"]
        for heading in ("School", "Casting Time", "Components", "Range",
                        "Duration", "Saving Throw"):
            assert heading in body, heading
        assert len(body) > 400

    def test_the_name_is_not_printed_twice(self, spell_lookup):
        """The dialog's heading says it; formatSpellObj leads with it as well,
        which is right in the picker where there is no heading over it."""
        assert "Gaseous Form" not in spell_lookup["clicked"]["body"]

    def test_it_shuts_again(self, spell_lookup):
        assert spell_lookup["closesAgain"] is True


class TestFindingTheSpellBehindTheName:
    def test_through_the_dc(self, spell_lookup):
        assert spell_lookup["throughTheDC"]["heading"] == "Suggestion"

    def test_through_the_source_book_without_eating_the_numeral(self, spell_lookup):
        """The book is a superscript after the name and the numeral is part of
        it, so "mental barrier IIOA" is Mental Barrier II out of Occult
        Adventures."""
        assert spell_lookup["throughTheSourceBook"]["heading"] == "Mental Barrier II"

    def test_through_a_rank_written_in_front(self, spell_lookup):
        """The table calls it "Dispel Magic, Greater"."""
        assert "dispel magic" in spell_lookup["rankInFront"]["heading"].lower()

    def test_a_class_feature_says_it_is_not_a_spell(self, spell_lookup):
        """A cleric's touch of evil is listed among the spell-like abilities
        but has no row in the spells table. Saying so beats an empty entry."""
        assert "No spell by that name" in spell_lookup["notASpell"]["note"]


class TestThePlayerSideOfIt:
    def test_the_player_gets_the_same_dialog(self, spell_lookup):
        assert spell_lookup["playerHeading"] == "Magic Missile"

    def test_with_the_rules_in_it(self, spell_lookup):
        assert "School" in spell_lookup["playerBody"]
        assert "Casting Time" in spell_lookup["playerBody"]


class TestTheSpellLookupRaisedNothing:
    def test_nothing_raised(self, spell_lookup):
        assert spell_lookup["errors"] == []


@pytest.fixture(scope="module")
def picker_spells(browser, live_server):
    """Spells in the statblock the monster picker shows.

    Choosing a monster is exactly when a GM wants to know what its spells do,
    and the picker is where that choice is made. The same statblock builder
    draws the unit sheet's entry, so this covers both.
    """
    context = browser.new_context(viewport={"width": 1500, "height": 1000})
    try:
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(live_server + "/")
        page.wait_for_function(
            "() => typeof socket !== 'undefined' && socket !== null && socket.connected",
            timeout=HANDSHAKE_TIMEOUT,
        )
        page.fill("#gameName", "picker spells")
        page.click("text=Create Game")
        page.wait_for_url("**/gm.html*", timeout=HANDSHAKE_TIMEOUT)
        page.wait_for_selector("#mapForm", state="attached")

        def preview(name):
            page.fill("#creatureSearchName", name)
            # Waiting for "any rows" is already true from the search before
            # this one, so it has to be this creature's row -- otherwise the
            # second search clicks the first search's result.
            page.wait_for_function(
                """(wanted) => {
                    const first = document.querySelector("#creatureRows tr");
                    return first && first.innerText.toLowerCase()
                        .includes(wanted.toLowerCase());
                }""",
                arg=name,
                timeout=HANDSHAKE_TIMEOUT,
            )
            page.click("#creatureRows tr:first-child td:first-child")
            page.wait_for_function(
                """(wanted) => {
                    const sb = document.querySelector(".statblock .sbName");
                    return sb && sb.innerText.toLowerCase()
                        .includes(wanted.toLowerCase());
                }""",
                arg=name,
                timeout=HANDSHAKE_TIMEOUT,
            )
            page.wait_for_timeout(300)

        page.click("div.tab:text-is('Encounter')")
        page.click("#chooseMonsterButton")
        page.wait_for_selector("#creatureSearchName")
        preview("adult occult dragon")

        stages = {}
        stages["names"] = page.eval_on_selector_all(
            ".statblock .spellLink", "els => els.map(e => e.innerText)")
        stages["text"] = page.inner_text(".statblock")
        # Every line that is a spell list, with what in it became a link.
        stages["lines"] = page.evaluate("""() => {
            return Array.from(document.querySelectorAll(".statblock .sbLine"))
                .map(l => ({
                    text: l.innerText.trim().slice(0, 40),
                    links: l.querySelectorAll(".spellLink").length,
                }))
                .filter(l => l.text);
        }""")

        # Opening one from inside the picker. Both are modals, and they used to
        # share an id.
        page.click(".statblock .spellLink >> text=gaseous form")
        page.wait_for_selector("#spellSheet", timeout=HANDSHAKE_TIMEOUT)
        page.wait_for_function(
            "() => !document.querySelector('.spellSheetNote')", timeout=HANDSHAKE_TIMEOUT)
        stages["opened"] = page.inner_text("#spellSheet .panelHeading")
        stages["pickerStillOpen"] = page.query_selector("#modalBackground") is not None
        stages["spellSitsOnTop"] = page.evaluate("""() => {
            const spell = Number(getComputedStyle(
                document.getElementById("spellModal")).zIndex);
            const picker = Number(getComputedStyle(
                document.getElementById("modalBackground")).zIndex);
            return spell > picker;
        }""")
        page.click("#spellModal", position={"x": 5, "y": 5})
        page.wait_for_timeout(300)
        stages["spellShut"] = page.query_selector("#spellSheet") is None
        stages["pickerSurvived"] = page.query_selector("#modalBackground") is not None

        # A cleric, for the Domains line -- those are domains, not spells.
        preview("Cultist of the Indomitable Sea")
        stages["domainLinks"] = page.evaluate("""() => {
            const line = Array.from(document.querySelectorAll(".statblock .sbLine"))
                .find(l => l.innerText.startsWith("Domains"));
            return line ? line.querySelectorAll(".spellLink").length : null;
        }""")

        stages["errors"] = errors
        return stages
    finally:
        context.close()


class TestSpellsInThePickersStatblock:
    def test_the_spells_are_clickable(self, picker_spells):
        names = picker_spells["names"]
        assert "gaseous form" in names
        assert "suggestion (DC 17)" in names

    def test_the_line_still_reads_the_way_it_does_in_the_book(self, picker_spells):
        """Only the spells become links. What says how often they can be cast
        stays as text, in front of them."""
        text = picker_spells["text"]
        for group in ("3rd (5/day)", "2nd (7/day)", "1st (8/day)", "0 (at-will)"):
            assert group in text, group

    def test_at_will_cantrips_are_clickable_too(self, picker_spells):
        """The group is written "0 (at-will)" here, with a hyphen. Against a
        pattern expecting a space it was not a group at all, so its cantrips
        ran on into the level above -- unlinked here, and counted as first
        level castings in the panel."""
        names = picker_spells["names"]
        assert "detect magic" in names
        assert "mage hand" in names

    def test_domains_are_not_spells(self, picker_spells):
        """"Evil, Water" are domains. Looked up as spells they would find
        nothing every time, so that line is left as text."""
        assert picker_spells["domainLinks"] == 0

    def test_no_line_is_all_link(self, picker_spells):
        """A sanity check that the label and the group marker stayed out of the
        links: a spell line has more text in it than its spells."""
        spell_lines = [l for l in picker_spells["lines"] if l["links"] > 0]
        assert spell_lines
        for line in spell_lines:
            assert "-" in line["text"] or "(" in line["text"], line


class TestASpellOpenedFromInsideThePicker:
    def test_it_opens(self, picker_spells):
        assert picker_spells["opened"] == "Gaseous Form"

    def test_the_picker_is_still_there_behind_it(self, picker_spells):
        assert picker_spells["pickerStillOpen"] is True

    def test_it_sits_on_top_of_the_picker(self, picker_spells):
        assert picker_spells["spellSitsOnTop"] is True

    def test_shutting_it_shuts_only_it(self, picker_spells):
        """Both are modals. Sharing #modalBackground meant getElementById found
        the picker first, so shutting the spell shut the picker instead and
        threw away the search that got there."""
        assert picker_spells["spellShut"] is True
        assert picker_spells["pickerSurvived"] is True


class TestThePickerSpellsRaisedNothing:
    def test_nothing_raised(self, picker_spells):
        assert picker_spells["errors"] == []


@pytest.fixture(scope="module")
def save_rolls(browser, live_server):
    """The buttons that roll a saving throw, on both views.

    A monster's saves come off its bestiary entry; a player's come off the
    total on their own sheet. Who sees the result follows who rolled, the same
    rule an attack roll goes by.
    """
    context = browser.new_context(viewport={"width": 1500, "height": 1000})
    try:
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(live_server + "/")
        page.wait_for_function(
            "() => typeof socket !== 'undefined' && socket !== null && socket.connected",
            timeout=HANDSHAKE_TIMEOUT,
        )
        page.fill("#gameName", "save rolls")
        page.click("text=Create Game")
        page.wait_for_url("**/gm.html*", timeout=HANDSHAKE_TIMEOUT)
        page.wait_for_selector("#mapForm", state="attached")
        room = dict(pair.split("=", 1)
                    for pair in page.url.split("?", 1)[1].split("&"))["room"]

        page.fill("#mapWidth", "14")
        page.fill("#mapHeight", "10")
        page.click("text=Generate Map")
        page.wait_for_function(
            "() => document.querySelectorAll('#mapGraphic .mapTile').length === 140",
            timeout=HANDSHAKE_TIMEOUT,
        )
        page.click("div.tab:text-is('Encounter')")
        page.click("#chooseMonsterButton")
        page.wait_for_selector("#creatureSearchName")
        page.fill("#creatureSearchName", "adult occult dragon")
        page.wait_for_function(
            "() => document.querySelectorAll('#creatureRows tr').length > 0",
            timeout=HANDSHAKE_TIMEOUT,
        )
        page.click("#creatureRows tr:first-child button")
        page.wait_for_function(
            "() => !document.getElementById('modalBackground')", timeout=HANDSHAKE_TIMEOUT)
        page.click("text=Add Unit")
        page.wait_for_function(
            """() => gmData && gmData.unitList.some(u => u.charName === "Adult Occult Dragon")""",
            timeout=HANDSHAKE_TIMEOUT,
        )
        # And one made by hand, which has no bestiary entry to take saves from.
        page.fill("#unitName", "Bandit")
        page.fill("#unitHP", "9")
        page.click("text=Add Unit")
        page.wait_for_function(
            """() => gmData && gmData.unitList.some(u => u.charName === "Bandit")""",
            timeout=HANDSHAKE_TIMEOUT,
        )
        page.wait_for_timeout(400)
        page.click("div.tab:text-is('Units')")
        page.click("#unitsDiv .unitListEntry")
        page.wait_for_timeout(600)
        page.click("div.tab:text-is('Map')")
        page.click("#bottomPopupButton")
        page.wait_for_timeout(900)

        stages = {}
        stages["parse"] = page.evaluate("""() => [
            parseSaves("Fort +13, Ref +9, Will +14"),
            parseSaves("Fortitude +3, Reflex +11, Will +5"),
            parseSaves("Fort +6, Ref +2, Will +7; +2 vs. fear"),
            parseSaves("Fort +5"),
        ]""")
        stages["buttons"] = page.eval_on_selector_all(
            "#mobPanelStats .saveRoll", "els => els.map(e => e.innerText)")

        before = page.inner_text("#chatText")
        page.click("#mobPanelStats .saveRoll >> nth=0")
        page.wait_for_function(
            "(was) => document.getElementById('chatText').innerText.length > was.length",
            arg=before, timeout=HANDSHAKE_TIMEOUT)
        stages["gmChat"] = page.inner_text("#chatText")[len(before):].strip()

        # A hand-made unit has no saves recorded, so it gets no buttons.
        page.evaluate(
            """() => { selectedUnits =
                 [gmData.unitList.find(u => u.charName === "Bandit").unitNum];
               drawMobPanel(gmData); }""")
        page.wait_for_timeout(500)
        stages["handMadeButtons"] = page.eval_on_selector_all(
            "#mobPanelStats .saveRoll", "els => els.length")
        stages["handMadeShows"] = page.eval_on_selector_all(
            "#mobPanelStats .mobStatNone", "els => els.map(e => e.innerText)")

        # The player's own save, off the total on their sheet.
        player = context.new_page()
        player.on("pageerror", lambda error: errors.append("player: " + str(error)))
        player.goto("%s/player.html?room=%s&charName=Vex" % (live_server, room))
        player.wait_for_function(
            "() => typeof socket !== 'undefined' && socket !== null && socket.connected",
            timeout=HANDSHAKE_TIMEOUT,
        )
        player.wait_for_timeout(800)
        stages["playerSawTheMonsterSave"] = (
            "Adult Occult Dragon" in player.inner_text("#chatText"))

        player.click("div.tab:text-is('Character')")
        player.wait_for_timeout(400)
        stages["playerButtons"] = player.eval_on_selector_all(
            ".saveRoll", "els => els.map(e => e.id)")
        player.evaluate(
            "() => { document.getElementById('sheetWillTotal').value = '7'; }")
        playerBefore = player.inner_text("#chatText")
        gmBefore = page.inner_text("#chatText")
        player.click("#rollWillSave")
        player.wait_for_function(
            "(was) => document.getElementById('chatText').innerText.length > was.length",
            arg=playerBefore, timeout=HANDSHAKE_TIMEOUT)
        stages["playerChat"] = player.inner_text("#chatText")[len(playerBefore):].strip()
        page.wait_for_function(
            "(was) => document.getElementById('chatText').innerText.length > was.length",
            arg=gmBefore, timeout=HANDSHAKE_TIMEOUT)
        stages["gmSawPlayerSave"] = page.inner_text("#chatText")[len(gmBefore):].strip()

        stages["errors"] = errors
        return stages
    finally:
        context.close()


class TestReadingSavesInTheBrowser:
    def test_the_usual_shape(self, save_rolls):
        assert save_rolls["parse"][0] == {"Fort": 13, "Ref": 9, "Will": 14}

    def test_written_out_in_full(self, save_rolls):
        assert save_rolls["parse"][1] == {"Fort": 3, "Ref": 11, "Will": 5}

    def test_a_note_after_the_numbers_is_not_one_of_them(self, save_rolls):
        assert save_rolls["parse"][2] == {"Fort": 6, "Ref": 2, "Will": 7}

    def test_a_save_that_is_not_written_is_absent(self, save_rolls):
        assert save_rolls["parse"][3] == {"Fort": 5}


class TestTheGmsSaveButtons:
    def test_one_button_per_save_with_the_modifier_on_it(self, save_rolls):
        """The button says what it is going to add before it is pressed, the
        same call the attack rows make by keeping the bonus in a box."""
        assert save_rolls["buttons"] == ["Fort +13", "Ref +9", "Will +14"]

    def test_pressing_one_rolls_it_into_the_chat(self, save_rolls):
        line = save_rolls["gmChat"]
        assert "Adult Occult Dragon" in line
        assert "Fort save" in line
        assert "d20(" in line and "+13" in line

    def test_a_unit_made_by_hand_gets_no_buttons(self, save_rolls):
        """Nothing to roll against, so a dash rather than three +0 buttons --
        which would be three rolls that mean nothing."""
        assert save_rolls["handMadeButtons"] == 0
        assert save_rolls["handMadeShows"] == ["—"]


class TestThePlayersSaveButtons:
    def test_there_is_one_beside_each_save(self, save_rolls):
        assert save_rolls["playerButtons"] == [
            "rollFortSave", "rollReflexSave", "rollWillSave"]

    def test_it_rolls_the_total_off_the_sheet(self, save_rolls):
        """From the total rather than the parts under it, so a player who has
        just corrected a number gets the number they are looking at."""
        line = save_rolls["playerChat"]
        assert "Vex" in line
        assert "Will save" in line
        assert "+7" in line


class TestWhoSeesASaveInTheBrowser:
    def test_the_party_is_not_told_the_monsters_save(self, save_rolls):
        """Learning that the dragon made its save is the game; learning that it
        made it by eleven is not."""
        assert save_rolls["playerSawTheMonsterSave"] is False

    def test_but_the_gm_sees_the_players_own(self, save_rolls):
        assert "Will save" in save_rolls["gmSawPlayerSave"]


class TestTheSaveRollsRaisedNothing:
    def test_nothing_raised(self, save_rolls):
        assert save_rolls["errors"] == []


@pytest.fixture(scope="module")
def warp_links(browser, live_server):
    """The tool that joins two tiles into a staircase.

    Two clicks rather than a paint, because a staircase is a pair. The first
    click marks the square and waits; the second finishes it, or -- on the same
    square -- takes an existing one out.
    """
    context = browser.new_context(viewport={"width": 1500, "height": 1000})
    try:
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(live_server + "/")
        page.wait_for_function(
            "() => typeof socket !== 'undefined' && socket !== null && socket.connected",
            timeout=HANDSHAKE_TIMEOUT,
        )
        page.fill("#gameName", "warp links")
        page.click("text=Create Game")
        page.wait_for_url("**/gm.html*", timeout=HANDSHAKE_TIMEOUT)
        page.wait_for_selector("#mapForm", state="attached")
        page.fill("#mapWidth", "20")
        page.fill("#mapHeight", "6")
        page.click("text=Generate Map")
        page.wait_for_function(
            "() => document.querySelectorAll('#mapGraphic .mapTile').length === 120",
            timeout=HANDSHAKE_TIMEOUT,
        )
        page.wait_for_timeout(400)

        def tile(x, y):
            # The ids carry a comma, which is not a selector on its own.
            return '[id="tile%d,%d"]' % (x, y)

        def marked(selector):
            return page.eval_on_selector_all(selector, "els => els.map(e => e.id).sort()")

        stages = {}
        stages["toolIsInThePalette"] = page.is_visible("#warpLink")

        page.click("#warpLink")
        page.click(tile(8, 2))
        page.wait_for_timeout(300)
        stages["pendingAfterFirstClick"] = marked(".warpPending")
        stages["linkedAfterFirstClick"] = marked(".warpTile")

        page.click(tile(12, 2))
        page.wait_for_timeout(600)
        stages["pendingAfterSecond"] = marked(".warpPending")
        stages["linkedAfterSecond"] = marked(".warpTile")
        stages["storedOnTheServer"] = page.evaluate(
            """() => [mapObject.mapArray[2][8].warp, mapObject.mapArray[2][12].warp]""")

        # Half a pair, then a change of tool: the pending mark must not sit
        # there waiting to catch the next square clicked.
        page.click(tile(4, 4))
        page.wait_for_timeout(250)
        stages["pendingBeforeToolChange"] = marked(".warpPending")
        page.click("#floorTile")
        page.wait_for_timeout(250)
        stages["pendingAfterToolChange"] = marked(".warpPending")

        # The same square twice unlinks it.
        page.click("#warpLink")
        page.click(tile(8, 2))
        page.wait_for_timeout(250)
        page.click(tile(8, 2))
        page.wait_for_timeout(600)
        stages["linkedAfterUnlink"] = marked(".warpTile")
        stages["clearedOnTheServer"] = page.evaluate(
            """() => [mapObject.mapArray[2][8].warp === undefined,
                      mapObject.mapArray[2][12].warp === undefined]""")

        stages["errors"] = errors
        return stages
    finally:
        context.close()


class TestTheStaircaseTool:
    def test_it_is_in_the_palette(self, warp_links):
        assert warp_links["toolIsInThePalette"] is True

    def test_the_first_click_marks_a_square_and_waits(self, warp_links):
        """Nothing is linked yet -- a staircase needs both ends."""
        assert warp_links["pendingAfterFirstClick"] == ["tile8,2"]
        assert warp_links["linkedAfterFirstClick"] == []

    def test_the_second_click_makes_the_pair(self, warp_links):
        assert warp_links["linkedAfterSecond"] == ["tile12,2", "tile8,2"]
        assert warp_links["pendingAfterSecond"] == []

    def test_both_ends_are_stored(self, warp_links):
        assert warp_links["storedOnTheServer"] == [[2, 12], [2, 8]]

    def test_changing_tool_abandons_a_half_made_pair(self, warp_links):
        """Left marked, it would join itself to whatever was clicked next."""
        assert warp_links["pendingBeforeToolChange"] == ["tile4,4"]
        assert warp_links["pendingAfterToolChange"] == []

    def test_the_same_square_twice_takes_a_staircase_out(self, warp_links):
        assert warp_links["linkedAfterUnlink"] == []

    def test_and_lets_go_of_both_ends(self, warp_links):
        """One end left pointing at the other would be a staircase to nowhere,
        still drawn as a staircase."""
        assert warp_links["clearedOnTheServer"] == [True, True]


class TestTheStaircaseToolRaisedNothing:
    def test_nothing_raised(self, warp_links):
        assert warp_links["errors"] == []


@pytest.fixture(scope="module")
def unit_token(browser, live_server):
    """Choosing a token for a unit, and whether the GM's own page notices.

    The GM does this from their unit sheet, so the GM is the one person who has
    to be told -- and was the one person who was not. The token went to the
    server and to the players, and the GM's page sat on the old one until it
    was reloaded.
    """
    context = browser.new_context(viewport={"width": 1500, "height": 1000})
    try:
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(live_server + "/")
        page.wait_for_function(
            "() => typeof socket !== 'undefined' && socket !== null && socket.connected",
            timeout=HANDSHAKE_TIMEOUT,
        )
        page.fill("#gameName", "unit token")
        page.click("text=Create Game")
        page.wait_for_url("**/gm.html*", timeout=HANDSHAKE_TIMEOUT)
        page.wait_for_selector("#mapForm", state="attached")
        page.fill("#mapWidth", "10")
        page.fill("#mapHeight", "6")
        page.click("text=Generate Map")
        page.wait_for_function(
            "() => document.querySelectorAll('#mapGraphic .mapTile').length === 60",
            timeout=HANDSHAKE_TIMEOUT,
        )
        page.click("div.tab:text-is('Encounter')")
        page.fill("#unitName", "Scout")
        page.fill("#unitHP", "10")
        page.click("text=Add Unit")
        page.wait_for_function(
            """() => gmData && gmData.unitList.some(u => u.charName === "Scout")""",
            timeout=HANDSHAKE_TIMEOUT,
        )
        page.wait_for_timeout(400)
        # On the board, so that a token has somewhere to be drawn.
        page.evaluate("""() => socket.emit('locate_unit', {selectedUnit: 0, moveType: 5,
            xCoord: 3, yCoord: 3, relative_x: 8, relative_y: 8,
            room: room, gmKey: gmKey})""")
        page.wait_for_timeout(600)
        page.click("div.tab:text-is('Units')")
        page.click("#unitsDiv .unitListEntry")
        page.wait_for_timeout(600)

        def report():
            return {
                "token": page.evaluate("() => gmData.unitList[0].token"),
                "sheetSrc": page.get_attribute("#unitTokenView", "src"),
                "onTheMap": page.eval_on_selector_all(
                    "#mapGraphic .tokenImg", "els => els.length"),
            }

        stages = {"before": report()}

        # What the dialog's Select button does for an image link. The dialog
        # itself is not the subject here; what happens after it is.
        page.evaluate(
            "(url) => sendChosenImage(url, 'unitToken', selectedUnits[0])",
            "/static/images/profile.svg")
        page.wait_for_timeout(1200)
        stages["after"] = report()

        stages["errors"] = errors
        return stages
    finally:
        context.close()


class TestChoosingAUnitToken:
    def test_it_starts_with_none(self, unit_token):
        assert unit_token["before"]["token"] == ""
        assert unit_token["before"]["onTheMap"] == 0

    def test_the_gm_is_told_without_reloading(self, unit_token):
        assert unit_token["after"]["token"] == "/static/images/profile.svg"

    def test_the_token_appears_on_the_board(self, unit_token):
        assert unit_token["after"]["onTheMap"] == 1

    def test_and_on_the_sheet_that_chose_it(self, unit_token):
        """An open sheet is deliberately not repopulated, since that would wipe
        what the GM was typing. The picture is not something they type into,
        and it is what they clicked to open the dialog in the first place."""
        assert unit_token["after"]["sheetSrc"] == "/static/images/profile.svg"


class TestChoosingAUnitTokenRaisedNothing:
    def test_nothing_raised(self, unit_token):
        assert unit_token["errors"] == []
