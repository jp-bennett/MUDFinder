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
        page.wait_for_timeout(300)
        stages["scaled"] = page.evaluate(BACKGROUND_GEOMETRY_JS)

        # Drag two squares right and one down, at 70px per square.
        box = page.locator("#mapContainer").bounding_box()
        page.mouse.move(box["x"] + 300, box["y"] + 300)
        page.mouse.down()
        page.mouse.move(box["x"] + 440, box["y"] + 370, steps=8)
        page.mouse.up()
        page.wait_for_timeout(400)
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
        page.wait_for_timeout(900)
        stages["rapid"] = page.evaluate(BACKGROUND_GEOMETRY_JS)
        # Every change sent has had its echo accounted for by now. This only
        # falls back to zero if the guard is actually wired into the handler.
        stages["sendsInFlight"] = page.evaluate("() => alignmentSendsInFlight")

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

        # The echo guard on its own. Losing the race on purpose is not
        # reproducible, so the rule it enforces is checked directly.
        stages["echo"] = page.evaluate("""() => {
            const own = {backgroundTilesWide: 99, backgroundOffsetX: 9, backgroundOffsetY: 9};
            alignmentSendsInFlight = 1;
            const droppedOwn = dropOwnAlignmentEcho(own);
            const other = {backgroundTilesWide: 99, backgroundOffsetX: 9, backgroundOffsetY: 9};
            const droppedOther = dropOwnAlignmentEcho(other);
            return {droppedOwn: droppedOwn,
                    ownStripped: !("backgroundTilesWide" in own),
                    droppedOther: droppedOther,
                    otherKept: "backgroundTilesWide" in other,
                    counter: alignmentSendsInFlight};
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
    """Alignment changes come back from the server, and a late echo of an
    earlier one must not undo a later local adjustment."""

    def test_our_own_echo_is_dropped(self, battlemap):
        assert battlemap["echo"]["droppedOwn"]

    def test_the_dropped_echo_carries_no_alignment_on(self, battlemap):
        """Stripped rather than ignored, so updateMap cannot apply it either."""
        assert battlemap["echo"]["ownStripped"]

    def test_a_change_from_elsewhere_is_kept(self, battlemap):
        """With nothing of ours outstanding, an update is somebody else's and
        has to be applied, or a second GM tab could never move the image."""
        assert not battlemap["echo"]["droppedOther"]
        assert battlemap["echo"]["otherKept"]

    def test_the_counter_is_spent(self, battlemap):
        assert battlemap["echo"]["counter"] == 0

    def test_the_guard_is_wired_into_the_handler(self, battlemap):
        """Three changes were sent and three echoes came back. A non-zero count
        means the handler is not consuming them, so the guard is inert."""
        assert battlemap["sendsInFlight"] == 0


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
        assert encounter["opened"]["initiativeLabel"] == "Initiative Count:"

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
        assert encounter["added"]["initiativeLabel"] == "Initiative Count:"


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
