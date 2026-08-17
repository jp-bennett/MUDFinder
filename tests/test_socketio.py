"""Tests for the Socket.IO event handlers.

This is the layer that broke silently when the server-side Socket.IO libraries
drifted ahead of the vendored 2.x browser client, so it is worth keeping
covered: if a dependency bump breaks the wire protocol or the handler
signatures, these fail rather than the app merely failing to work in a browser.
"""

import pytest

import mudfinder
from helpers import GM_KEY, event, event_names


class TestConnection:
    def test_client_connects(self, client):
        assert client.is_connected()

    def test_client_disconnects(self, client):
        client.disconnect()
        assert not client.is_connected()


class TestCreateRoom:
    def test_create_emits_create_room(self, client):
        client.emit("create", {"name": "My Game", "gmKey": GM_KEY})
        assert "create_room" in event_names(client.get_received())

    def test_create_registers_the_room(self, client):
        client.emit("create", {"name": "My Game", "gmKey": GM_KEY})
        room = event(client.get_received(), "create_room")["args"][0]["room"]
        assert room in mudfinder.ROOMS

    def test_create_room_payload_carries_the_gm_url(self, client):
        client.emit("create", {"name": "My Game", "gmKey": GM_KEY})
        payload = event(client.get_received(), "create_room")["args"][0]
        assert payload["name"] == "My Game"
        assert payload["url"].startswith("gm.html?gmKey=%s&room=" % GM_KEY)

    def test_session_records_the_supplied_name(self, client):
        client.emit("create", {"name": "My Game", "gmKey": GM_KEY})
        room = event(client.get_received(), "create_room")["args"][0]["room"]
        assert mudfinder.ROOMS[room].name == "My Game"


class TestJoinGm:
    def test_correct_key_receives_map_and_state(self, client):
        client.emit("create", {"name": "G", "gmKey": GM_KEY})
        room = event(client.get_received(), "create_room")["args"][0]["room"]
        client.emit("join_gm", {"room": room, "gmKey": GM_KEY})
        received = event_names(client.get_received())
        assert "gm_map" in received
        assert "gm_update" in received

    def test_wrong_key_is_rejected(self, client):
        client.emit("create", {"name": "G", "gmKey": GM_KEY})
        room = event(client.get_received(), "create_room")["args"][0]["room"]
        client.emit("join_gm", {"room": room, "gmKey": "wrong-key"})
        received = client.get_received()
        assert event_names(received) == ["error"]

    def test_unknown_room_is_rejected(self, client):
        client.emit("join_gm", {"room": "no-such-room", "gmKey": GM_KEY})
        assert event_names(client.get_received()) == ["error"]

    def test_gm_update_carries_the_session_state(self, gm):
        client, room, key = gm
        client.emit("join_gm", {"room": room, "gmKey": key})
        state = event(client.get_received(), "gm_update")["args"][0]
        assert state["name"] == "Test Game"
        assert state["room"] == room


class TestPlayerJoin:
    def test_player_receives_map_and_update(self, gm):
        _, room, _ = gm
        player = mudfinder.socketio.test_client(mudfinder.app)
        player.emit("player_join", {"room": room, "charName": "Aria"})
        received = event_names(player.get_received())
        assert "draw_map" in received
        assert "do_update" in received

    def test_player_is_registered_on_the_session(self, gm):
        _, room, _ = gm
        player = mudfinder.socketio.test_client(mudfinder.app)
        player.emit("player_join", {"room": room, "charName": "Aria"})
        assert "Aria" in mudfinder.ROOMS[room].playerList
        assert mudfinder.ROOMS[room].playerList["Aria"].connected is True

    def test_player_is_added_to_the_unit_list(self, gm):
        _, room, _ = gm
        player = mudfinder.socketio.test_client(mudfinder.app)
        player.emit("player_join", {"room": room, "charName": "Aria"})
        assert [u.charName for u in mudfinder.ROOMS[room].unitList] == ["Aria"]

    def test_rejoining_does_not_duplicate_the_player(self, gm):
        _, room, _ = gm
        for _ in range(2):
            player = mudfinder.socketio.test_client(mudfinder.app)
            player.emit("player_join", {"room": room, "charName": "Aria"})
        assert len(mudfinder.ROOMS[room].unitList) == 1
        assert mudfinder.ROOMS[room].playerList["Aria"].connections == 2

    def test_unknown_room_is_rejected(self, client):
        client.emit("player_join", {"room": "no-such-room", "charName": "Aria"})
        assert event_names(client.get_received()) == ["error"]

    def test_the_gm_is_notified_of_the_join(self, gm):
        """Without this the GM's lists stay stale until an unrelated event."""
        gm_client, room, _ = gm
        player = mudfinder.socketio.test_client(mudfinder.app)
        player.emit("player_join", {"room": room, "charName": "Aria"})
        assert "gm_update" in event_names(gm_client.get_received())

    def test_the_gm_update_contains_the_new_player(self, gm):
        gm_client, room, _ = gm
        player = mudfinder.socketio.test_client(mudfinder.app)
        player.emit("player_join", {"room": room, "charName": "Aria"})
        state = event(gm_client.get_received(), "gm_update")["args"][0]
        assert "Aria" in state["playerList"]


class TestChat:
    def test_player_message_is_broadcast(self, gm):
        gm_client, room, _ = gm
        player = mudfinder.socketio.test_client(mudfinder.app)
        player.emit("player_join", {"room": room, "charName": "Aria"})
        player.get_received()
        gm_client.get_received()

        player.emit("chat", {"room": room, "chat": "hello", "charName": "Aria"})
        messages = [p["args"][0]["chat"] for p in player.get_received() if p["name"] == "chat"]
        assert "hello" in messages

    def test_gm_message_requires_the_gm_key(self, gm):
        gm_client, room, _ = gm
        gm_client.emit("chat", {"room": room, "chat": "hi", "charName": "gm", "gmKey": "wrong"})
        assert gm_client.get_received() == []

    def test_gm_message_with_the_right_key_is_sent(self, gm):
        gm_client, room, key = gm
        gm_client.emit("chat", {"room": room, "chat": "hi", "charName": "gm", "gmKey": key})
        messages = [p["args"][0]["chat"] for p in gm_client.get_received()]
        assert "hi" in messages

    def test_empty_message_is_dropped(self, gm):
        gm_client, room, key = gm
        gm_client.emit("chat", {"room": room, "chat": "", "charName": "gm", "gmKey": key})
        assert gm_client.get_received() == []

    def test_roll_command_emits_a_result(self, gm):
        gm_client, room, key = gm
        gm_client.emit("chat", {"room": room, "chat": "/roll 1d1", "charName": "gm", "gmKey": key})
        messages = [p["args"][0]["chat"] for p in gm_client.get_received()]
        # The command itself is echoed, then the evaluated result.
        assert "/roll 1d1" in messages
        assert "1 " in messages

    def test_roll_is_case_insensitive(self, gm):
        gm_client, room, key = gm
        gm_client.emit("chat", {"room": room, "chat": "/ROLL 1d1", "charName": "gm", "gmKey": key})
        messages = [p["args"][0]["chat"] for p in gm_client.get_received()]
        assert "1 " in messages

    def test_plain_message_is_not_evaluated(self, gm):
        gm_client, room, key = gm
        gm_client.emit("chat", {"room": room, "chat": "roll for it", "charName": "gm", "gmKey": key})
        messages = [p["args"][0]["chat"] for p in gm_client.get_received()]
        assert messages and all(m == "roll for it" for m in messages)


class TestUnits:
    def test_gm_can_add_a_unit(self, gm):
        gm_client, room, key = gm
        gm_client.emit("add_unit", {
            "room": room, "gmKey": key,
            "unit": {"charName": "Goblin"}, "addToInitiative": False,
        })
        assert [u.charName for u in mudfinder.ROOMS[room].unitList] == ["Goblin"]

    def test_adding_with_initiative_puts_the_unit_in_the_order(self, gm):
        gm_client, room, key = gm
        gm_client.emit("add_unit", {
            "room": room, "gmKey": key,
            "unit": {"charName": "Goblin", "initiative": 15}, "addToInitiative": True,
        })
        session = mudfinder.ROOMS[room]
        assert [u.charName for u in session.initiativeList] == ["Goblin"]
        assert session.unitList[0].inInit is True
        assert session.unitList[0].flatFooted is True

    def test_added_units_are_numbered(self, gm):
        gm_client, room, key = gm
        for name in ["A", "B"]:
            gm_client.emit("add_unit", {
                "room": room, "gmKey": key,
                "unit": {"charName": name}, "addToInitiative": False,
            })
        assert [u.unitNum for u in mudfinder.ROOMS[room].unitList] == [0, 1]

    def test_adding_a_unit_notifies_the_gm(self, gm):
        gm_client, room, key = gm
        gm_client.emit("add_unit", {
            "room": room, "gmKey": key,
            "unit": {"charName": "Goblin"}, "addToInitiative": False,
        })
        assert "gm_update" in event_names(gm_client.get_received())

    def test_unknown_room_is_ignored(self, client):
        client.emit("add_unit", {
            "room": "no-such-room", "gmKey": GM_KEY,
            "unit": {"charName": "Goblin"}, "addToInitiative": False,
        })
        assert client.get_received() == []


class TestMapGenerate:
    def test_gm_can_generate_a_map(self, gm):
        gm_client, room, key = gm
        gm_client.emit("map_generate", {
            "room": room, "gmKey": key,
            "mapWidth": 4, "mapHeight": 3, "discovered": False,
        })
        grid = mudfinder.ROOMS[room].mapData["mapArray"]
        assert len(grid) == 3
        assert all(len(row) == 4 for row in grid)

    def test_generated_tiles_are_walkable_floor(self, gm):
        gm_client, room, key = gm
        gm_client.emit("map_generate", {
            "room": room, "gmKey": key,
            "mapWidth": 2, "mapHeight": 2, "discovered": True,
        })
        tile = mudfinder.ROOMS[room].mapData["mapArray"][0][0]
        assert tile["tile"] == "floorTile"
        assert tile["walkable"] is True
        assert tile["seen"] is True

    def test_tiles_carry_their_coordinates(self, gm):
        gm_client, room, key = gm
        gm_client.emit("map_generate", {
            "room": room, "gmKey": key,
            "mapWidth": 3, "mapHeight": 2, "discovered": False,
        })
        grid = mudfinder.ROOMS[room].mapData["mapArray"]
        assert (grid[1][2]["x"], grid[1][2]["y"]) == (2, 1)

    def test_generating_emits_maps_to_both_views(self, gm):
        gm_client, room, key = gm
        gm_client.emit("map_generate", {
            "room": room, "gmKey": key,
            "mapWidth": 2, "mapHeight": 2, "discovered": False,
        })
        assert "gm_map" in event_names(gm_client.get_received())

    def test_wrong_key_cannot_generate(self, gm):
        gm_client, room, _ = gm
        gm_client.emit("map_generate", {
            "room": room, "gmKey": "wrong",
            "mapWidth": 2, "mapHeight": 2, "discovered": False,
        })
        assert mudfinder.ROOMS[room].mapData["mapArray"] == []


class TestSpellDatabase:
    """These read the bundled SQLite file, so they also assert it is present."""

    def test_wizard_level_one_spells_are_returned(self, client):
        spells = client.emit("database_spells", "Wizard", "1", callback=True)
        assert len(spells) > 100
        assert all(spell["level"] == "1" for spell in spells)

    def test_spell_rows_carry_a_name(self, client):
        spells = client.emit("database_spells", "Wizard", "1", callback=True)
        assert all(spell["name"] for spell in spells)

    def test_arcanist_is_mapped_onto_the_wizard_list(self, client):
        wizard = client.emit("database_spells", "Wizard", "1", callback=True)
        arcanist = client.emit("database_spells", "Arcanist", "1", callback=True)
        assert [s["name"] for s in wizard] == [s["name"] for s in arcanist]

    def test_cleric_list_differs_from_wizard(self, client):
        wizard = client.emit("database_spells", "Wizard", "1", callback=True)
        cleric = client.emit("database_spells", "Cleric", "1", callback=True)
        assert [s["name"] for s in wizard] != [s["name"] for s in cleric]

    def test_unknown_class_returns_nothing(self, client):
        assert client.emit("database_spells", "Nonsense", "1", callback=True) == []

    @pytest.mark.parametrize("caster_class", [
        "wiz; drop table spells--",
        "wiz or 1=1",
        "1) --",
        "",
    ])
    def test_a_class_name_is_never_interpolated_into_the_query(self, client, caster_class):
        """The column comes from SPELL_CLASS_COLUMNS, never from the client."""
        assert client.emit("database_spells", caster_class, "1", callback=True) == []

    def test_the_spells_table_survives_a_hostile_class_name(self, client):
        client.emit("database_spells", "wiz; drop table spells--", "1", callback=True)
        assert len(client.emit("database_spells", "Wizard", "1", callback=True)) > 100

    def test_creature_lookup_by_cr(self, client):
        client.emit("database_creatures", {"cr": "1"})
        creatures = event(client.get_received(), "database_creatures_response")["args"][0]
        assert len(creatures) > 0


class TestImages:
    def test_request_images_returns_the_room_image_map(self, gm):
        gm_client, room, _ = gm
        assert gm_client.emit("request_images", room, callback=True) == {}

    def test_request_images_for_an_unknown_room(self, client):
        # The handler returns None; the test client reports "no callback data"
        # as an empty list.
        assert not client.emit("request_images", "no-such-room", callback=True)


BATTLEMAP_IMAGE = "https://example.invalid/gunalley.png"
DEFAULT_BACKGROUND = "static/images/mapbackground.jpg"


def set_background(gm_client, room, image=BATTLEMAP_IMAGE):
    gm_client.emit("image_upload", room, image, "mapBackground", "")
    gm_client.get_received()


class TestMapGenerateOverBackground:
    """Laying a grid over an uploaded battlemap.

    map_generate resets the background to the default parchment, so a battlemap
    cannot be made by generating first and uploading second, and uploading
    first then generating throws the image away. This is the path that works.
    """

    def test_it_builds_the_requested_grid(self, gm):
        gm_client, room, key = gm
        set_background(gm_client, room)
        gm_client.emit("map_generate_over_background", {
            "room": room, "gmKey": key,
            "mapWidth": 22, "mapHeight": 34, "discovered": False,
        })
        grid = mudfinder.ROOMS[room].mapData["mapArray"]
        assert len(grid) == 34
        assert all(len(row) == 22 for row in grid)

    def test_it_keeps_the_background(self, gm):
        """The whole point: map_generate would have discarded it."""
        gm_client, room, key = gm
        set_background(gm_client, room)
        gm_client.emit("map_generate_over_background", {
            "room": room, "gmKey": key,
            "mapWidth": 4, "mapHeight": 3, "discovered": False,
        })
        assert mudfinder.ROOMS[room].mapData["mapBackground"] == BATTLEMAP_IMAGE

    def test_plain_generate_still_discards_the_background(self, gm):
        """Guards the contrast, so the two paths cannot quietly converge."""
        gm_client, room, key = gm
        set_background(gm_client, room)
        gm_client.emit("map_generate", {
            "room": room, "gmKey": key,
            "mapWidth": 4, "mapHeight": 3, "discovered": False,
        })
        assert mudfinder.ROOMS[room].mapData["mapBackground"] == DEFAULT_BACKGROUND

    def test_it_seeds_alignment_spanning_the_grid(self, gm):
        gm_client, room, key = gm
        set_background(gm_client, room)
        gm_client.emit("map_generate_over_background", {
            "room": room, "gmKey": key,
            "mapWidth": 22, "mapHeight": 34, "discovered": False,
        })
        map_data = mudfinder.ROOMS[room].mapData
        assert map_data["backgroundTilesWide"] == 22
        assert map_data["backgroundOffsetX"] == 0
        assert map_data["backgroundOffsetY"] == 0

    def test_tiles_have_the_same_shape_as_a_generated_map(self, gm):
        gm_client, room, key = gm
        gm_client.emit("map_generate_over_background", {
            "room": room, "gmKey": key,
            "mapWidth": 2, "mapHeight": 2, "discovered": True,
        })
        tile = mudfinder.ROOMS[room].mapData["mapArray"][1][0]
        assert tile == {"tile": "floorTile", "walkable": True, "seen": True,
                        "secret": False, "x": 0, "y": 1}

    def test_wrong_key_cannot_build(self, gm):
        gm_client, room, _ = gm
        gm_client.emit("map_generate_over_background", {
            "room": room, "gmKey": "wrong",
            "mapWidth": 4, "mapHeight": 3, "discovered": False,
        })
        assert mudfinder.ROOMS[room].mapData["mapArray"] == []

    def test_unknown_room_is_ignored(self, client):
        client.emit("map_generate_over_background", {
            "room": "no-such-room", "gmKey": GM_KEY,
            "mapWidth": 4, "mapHeight": 3, "discovered": False,
        })
        assert client.get_received() == []


class TestBackgroundAlignment:
    """Placing the image against the grid, in grid squares."""

    def align(self, gm_client, room, key, wide=24.5, x=-1.25, y=-0.8):
        gm_client.emit("set_background_alignment", {
            "room": room, "gmKey": key,
            "backgroundTilesWide": wide, "backgroundOffsetX": x, "backgroundOffsetY": y,
        })

    def test_the_values_are_stored(self, gm):
        gm_client, room, key = gm
        self.align(gm_client, room, key)
        map_data = mudfinder.ROOMS[room].mapData
        assert map_data["backgroundTilesWide"] == 24.5
        assert map_data["backgroundOffsetX"] == -1.25
        assert map_data["backgroundOffsetY"] == -0.8

    def test_it_reaches_the_gm(self, gm):
        gm_client, room, key = gm
        self.align(gm_client, room, key)
        assert "gm_map_update" in event_names(gm_client.get_received())

    def test_it_carries_no_tiles(self, gm):
        """Only the background moves; nothing should be redrawn."""
        gm_client, room, key = gm
        self.align(gm_client, room, key)
        payload = event(gm_client.get_received(), "gm_map_update")["args"][0]
        assert payload["mapArray"] == []
        assert payload["backgroundTilesWide"] == 24.5

    def test_it_reaches_players(self, gm):
        gm_client, room, key = gm
        player = mudfinder.socketio.test_client(mudfinder.app)
        player.emit("player_join", {"room": room, "charName": "Aria"})
        player.get_received()

        self.align(gm_client, room, key)
        payload = event(player.get_received(), "player_map_update")["args"][0]
        assert payload["backgroundTilesWide"] == 24.5
        assert payload["backgroundOffsetX"] == -1.25

    def test_wrong_key_changes_nothing(self, gm):
        gm_client, room, key = gm
        self.align(gm_client, room, key)
        gm_client.get_received()
        self.align(gm_client, room, "wrong", wide=99)
        assert mudfinder.ROOMS[room].mapData["backgroundTilesWide"] == 24.5

    def test_unknown_room_is_ignored(self, client):
        client.emit("set_background_alignment", {
            "room": "no-such-room", "gmKey": GM_KEY,
            "backgroundTilesWide": 5, "backgroundOffsetX": 0, "backgroundOffsetY": 0,
        })
        assert client.get_received() == []

    @pytest.mark.parametrize("bad", ["abc", None, "", [1], float("nan"), float("inf")])
    def test_values_that_are_not_numbers_are_refused(self, gm, bad):
        """These come from a GM's text field, so junk must not wedge the map."""
        gm_client, room, key = gm
        self.align(gm_client, room, key)
        gm_client.get_received()
        self.align(gm_client, room, key, wide=bad)
        assert mudfinder.ROOMS[room].mapData["backgroundTilesWide"] == 24.5

    def test_an_absurd_scale_is_clamped(self, gm):
        gm_client, room, key = gm
        self.align(gm_client, room, key, wide=99999)
        assert mudfinder.ROOMS[room].mapData["backgroundTilesWide"] == mudfinder.MAX_BACKGROUND_TILES_WIDE

    def test_a_zero_scale_is_clamped(self, gm):
        """Zero squares wide would make the image vanish."""
        gm_client, room, key = gm
        self.align(gm_client, room, key, wide=0)
        assert mudfinder.ROOMS[room].mapData["backgroundTilesWide"] == mudfinder.MIN_BACKGROUND_TILES_WIDE

    def test_negative_offsets_are_allowed(self, gm):
        """Pulling the image up and left is the normal case: it trims a border."""
        gm_client, room, key = gm
        self.align(gm_client, room, key, x=-3.5, y=-2.25)
        map_data = mudfinder.ROOMS[room].mapData
        assert map_data["backgroundOffsetX"] == -3.5
        assert map_data["backgroundOffsetY"] == -2.25

    def test_clearing_the_map_drops_the_alignment(self, gm):
        gm_client, room, key = gm
        self.align(gm_client, room, key)
        gm_client.emit("clear_map", {"room": room, "gmKey": key, "clearLocations": True})
        assert "backgroundTilesWide" not in mudfinder.ROOMS[room].mapData


class TestUploadLimit:
    """Images arrive over the socket, and the transport's own cap decides
    whether an ordinary battlemap survives the trip."""

    def test_the_transport_accepts_more_than_the_default_megabyte(self):
        """A megabyte is roughly a 750kB image once base64 has grown it."""
        assert mudfinder.socketio.server.eio.max_http_buffer_size > 1000000

    def test_it_matches_what_the_client_enforces(self):
        """shared.js refuses anything larger before it reaches the wire, so the
        two numbers have to agree or one of them is decorative."""
        client_side = open("static/js/shared.js").read()
        assert "var MAX_UPLOAD_BYTES = 16 * 1024 * 1024;" in client_side
        assert mudfinder.MAX_UPLOAD_BYTES == 16 * 1024 * 1024
        assert mudfinder.socketio.server.eio.max_http_buffer_size == mudfinder.MAX_UPLOAD_BYTES


class TestMapResize:
    """Changing how many squares a map is, without losing what is on it.

    The square count is the hard thing to know before the grid is sitting on
    the artwork, so it has to be adjustable during alignment rather than fixed
    when the map is made.
    """

    def battlemap(self, gm_client, room, key, width=6, height=5):
        set_background(gm_client, room)
        gm_client.emit("map_generate_over_background", {
            "room": room, "gmKey": key,
            "mapWidth": width, "mapHeight": height, "discovered": False,
        })
        gm_client.get_received()

    def test_growing_the_grid(self, gm):
        gm_client, room, key = gm
        self.battlemap(gm_client, room, key)
        gm_client.emit("map_resize", {"room": room, "gmKey": key, "mapWidth": 9, "mapHeight": 7})
        grid = mudfinder.ROOMS[room].mapData["mapArray"]
        assert len(grid) == 7
        assert all(len(row) == 9 for row in grid)

    def test_shrinking_the_grid(self, gm):
        gm_client, room, key = gm
        self.battlemap(gm_client, room, key)
        gm_client.emit("map_resize", {"room": room, "gmKey": key, "mapWidth": 3, "mapHeight": 2})
        grid = mudfinder.ROOMS[room].mapData["mapArray"]
        assert len(grid) == 2
        assert all(len(row) == 3 for row in grid)

    def test_tiles_inside_the_new_bounds_are_kept(self, gm):
        """Otherwise adjusting the count would throw away a painted map."""
        gm_client, room, key = gm
        self.battlemap(gm_client, room, key)
        mudfinder.ROOMS[room].mapData["mapArray"][1][2]["tile"] = "wallTile"
        gm_client.emit("map_resize", {"room": room, "gmKey": key, "mapWidth": 9, "mapHeight": 7})
        assert mudfinder.ROOMS[room].mapData["mapArray"][1][2]["tile"] == "wallTile"

    def test_new_ground_is_plain_floor(self, gm):
        gm_client, room, key = gm
        self.battlemap(gm_client, room, key)
        gm_client.emit("map_resize", {"room": room, "gmKey": key, "mapWidth": 9, "mapHeight": 7})
        assert mudfinder.ROOMS[room].mapData["mapArray"][6][8] == {
            "tile": "floorTile", "walkable": True, "seen": False,
            "secret": False, "x": 8, "y": 6}

    def test_the_background_and_its_alignment_are_untouched(self, gm):
        """Resizing says nothing about how big the artwork should be."""
        gm_client, room, key = gm
        self.battlemap(gm_client, room, key)
        gm_client.emit("set_background_alignment", {
            "room": room, "gmKey": key,
            "backgroundTilesWide": 12.4, "backgroundOffsetX": -1.2, "backgroundOffsetY": -0.8,
        })
        gm_client.emit("map_resize", {"room": room, "gmKey": key, "mapWidth": 9, "mapHeight": 7})
        map_data = mudfinder.ROOMS[room].mapData
        assert map_data["mapBackground"] == BATTLEMAP_IMAGE
        assert map_data["backgroundTilesWide"] == 12.4
        assert map_data["backgroundOffsetX"] == -1.2

    def test_a_unit_left_outside_is_taken_off_the_map(self, gm):
        """The views look tiles up by coordinate, so a unit past the edge has
        nothing to stand on."""
        gm_client, room, key = gm
        self.battlemap(gm_client, room, key)
        gm_client.emit("add_unit", {
            "room": room, "gmKey": key, "addToInitiative": False,
            "unit": {"charName": "Goblin", "x": 5, "y": 4},
        })
        gm_client.emit("map_resize", {"room": room, "gmKey": key, "mapWidth": 3, "mapHeight": 2})
        goblin = mudfinder.ROOMS[room].unitList[0]
        assert (goblin.x, goblin.y) == (-1, -1)

    def test_a_unit_still_inside_keeps_its_place(self, gm):
        gm_client, room, key = gm
        self.battlemap(gm_client, room, key)
        gm_client.emit("add_unit", {
            "room": room, "gmKey": key, "addToInitiative": False,
            "unit": {"charName": "Goblin", "x": 1, "y": 1},
        })
        gm_client.emit("map_resize", {"room": room, "gmKey": key, "mapWidth": 3, "mapHeight": 2})
        goblin = mudfinder.ROOMS[room].unitList[0]
        assert (goblin.x, goblin.y) == (1, 1)

    def test_the_players_are_sent_the_new_map(self, gm):
        gm_client, room, key = gm
        self.battlemap(gm_client, room, key)
        player = mudfinder.socketio.test_client(mudfinder.app)
        player.emit("player_join", {"room": room, "charName": "Aria"})
        player.get_received()
        gm_client.emit("map_resize", {"room": room, "gmKey": key, "mapWidth": 3, "mapHeight": 2})
        assert "draw_map" in event_names(player.get_received())

    def test_wrong_key_cannot_resize(self, gm):
        gm_client, room, key = gm
        self.battlemap(gm_client, room, key)
        gm_client.emit("map_resize", {"room": room, "gmKey": "wrong", "mapWidth": 3, "mapHeight": 2})
        assert len(mudfinder.ROOMS[room].mapData["mapArray"]) == 5

    @pytest.mark.parametrize("bad", ["abc", None, 0, -4, ""])
    def test_a_size_that_is_not_a_usable_number_is_refused(self, gm, bad):
        gm_client, room, key = gm
        self.battlemap(gm_client, room, key)
        gm_client.emit("map_resize", {"room": room, "gmKey": key, "mapWidth": bad, "mapHeight": 4})
        assert len(mudfinder.ROOMS[room].mapData["mapArray"][0]) == 6

    def test_an_absurd_size_is_clamped(self, gm):
        """The grid is built by iterating this, so a mistyped number would
        otherwise sit there allocating tiles."""
        gm_client, room, key = gm
        self.battlemap(gm_client, room, key)
        gm_client.emit("map_resize", {
            "room": room, "gmKey": key, "mapWidth": 100000, "mapHeight": 2})
        assert len(mudfinder.ROOMS[room].mapData["mapArray"][0]) == mudfinder.MAX_MAP_DIMENSION

    def test_building_over_a_background_is_clamped_too(self, gm):
        gm_client, room, key = gm
        set_background(gm_client, room)
        gm_client.emit("map_generate_over_background", {
            "room": room, "gmKey": key,
            "mapWidth": 100000, "mapHeight": 2, "discovered": False,
        })
        assert len(mudfinder.ROOMS[room].mapData["mapArray"][0]) == mudfinder.MAX_MAP_DIMENSION
