"""Tests for the Socket.IO event handlers.

This is the layer that broke silently when the server-side Socket.IO libraries
drifted ahead of the vendored 2.x browser client, so it is worth keeping
covered: if a dependency bump breaks the wire protocol or the handler
signatures, these fail rather than the app merely failing to work in a browser.
"""

import re

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


class TestMapUpload:
    """Pasting a map exported from a dungeon generator.

    The TSV is typed or pasted by hand, so it is the one map source that
    arrives in whatever shape the GM's clipboard was in.
    """

    def upload(self, gm_client, room, key, text, discovered=False):
        gm_client.emit("map_upload", {
            "room": room, "gmKey": key, "mapText": text, "discovered": discovered,
        })

    def test_a_pasted_map_becomes_a_grid(self, gm):
        gm_client, room, key = gm
        self.upload(gm_client, room, key, "F\tF\tD\nF\tF\tSU\n")
        grid = mudfinder.ROOMS[room].mapData["mapArray"]
        assert [tile["tile"] for tile in grid[0]] == ["floorTile", "floorTile", "doorClosed"]
        assert [tile["tile"] for tile in grid[1]] == ["floorTile", "floorTile", "stairsUp"]

    def test_the_map_is_drawn_without_a_reload(self, gm):
        """Every other way of making a map redraws; this one used to leave the
        new grid sitting on the server until someone refreshed the page."""
        gm_client, room, key = gm
        player = mudfinder.socketio.test_client(mudfinder.app)
        player.emit("player_join", {"room": room, "charName": "Aria"})
        player.get_received()
        self.upload(gm_client, room, key, "F\tF\nF\tF\n")
        assert "gm_map" in event_names(gm_client.get_received())
        assert "draw_map" in event_names(player.get_received())

    def test_windows_line_endings_parse(self, gm):
        """A map saved from a text editor on Windows, or pasted out of one,
        arrives with a carriage return stuck to the last cell of every row.
        "F\\r" matched none of the tile codes, so the row was left one tile
        short and the parse then indexed off the end of it."""
        gm_client, room, key = gm
        self.upload(gm_client, room, key, "F\tF\r\nD\tSU\r\n")
        grid = mudfinder.ROOMS[room].mapData["mapArray"]
        assert [tile["tile"] for tile in grid[0]] == ["floorTile", "floorTile"]
        assert [tile["tile"] for tile in grid[1]] == ["doorClosed", "stairsUp"]

    def test_a_trailing_newline_does_not_add_a_row(self, gm):
        """Text ends with a newline, so the map was a row of walls taller than
        the one the GM pasted."""
        gm_client, room, key = gm
        self.upload(gm_client, room, key, "F\tF\nF\tF\n")
        assert len(mudfinder.ROOMS[room].mapData["mapArray"]) == 2

    def test_an_unrecognised_code_becomes_a_wall(self, gm):
        """It used to append no tile at all, and then index off the end of the
        row it had just failed to fill, taking the whole paste down."""
        gm_client, room, key = gm
        self.upload(gm_client, room, key, "F\tQ\tF\n")
        row = mudfinder.ROOMS[room].mapData["mapArray"][0]
        assert len(row) == 3
        assert row[1] == {"tile": "wallTile", "walkable": False, "seen": False,
                          "secret": False, "x": 1, "y": 0}

    def test_a_blank_cell_is_still_a_wall(self, gm):
        gm_client, room, key = gm
        self.upload(gm_client, room, key, "F\t\tF\n")
        assert mudfinder.ROOMS[room].mapData["mapArray"][0][1]["tile"] == "wallTile"

    def test_a_secret_door_is_marked_secret(self, gm):
        gm_client, room, key = gm
        self.upload(gm_client, room, key, "F\tDS\n")
        assert mudfinder.ROOMS[room].mapData["mapArray"][0][1]["secret"] is True

    def test_an_enormous_paste_is_clamped(self, gm):
        """Nothing about a clipboard bounds this, and the grid is iterated to
        build it, so the size has to be capped somewhere."""
        gm_client, room, key = gm
        row = "\t".join(["F"] * 1000)
        self.upload(gm_client, room, key, "\n".join([row] * 1000))
        grid = mudfinder.ROOMS[room].mapData["mapArray"]
        assert len(grid) == mudfinder.MAX_MAP_DIMENSION
        assert len(grid[0]) == mudfinder.MAX_MAP_DIMENSION

    def test_uploading_clears_stale_alignment(self, gm):
        """The pasted map replaces the background with the default parchment,
        so alignment measured against the old artwork would misplace it."""
        gm_client, room, key = gm
        set_background(gm_client, room)
        gm_client.emit("map_generate_over_background", {
            "room": room, "gmKey": key,
            "mapWidth": 4, "mapHeight": 3, "discovered": False,
        })
        self.upload(gm_client, room, key, "F\tF\n")
        map_data = mudfinder.ROOMS[room].mapData
        assert map_data["mapBackground"] == DEFAULT_BACKGROUND
        assert "backgroundTilesWide" not in map_data

    def test_wrong_key_cannot_upload(self, gm):
        gm_client, room, _ = gm
        self.upload(gm_client, room, "wrong", "F\tF\n")
        assert mudfinder.ROOMS[room].mapData["mapArray"] == []


class TestMapGenerateLimits:
    def test_an_absurd_size_is_clamped(self, gm):
        gm_client, room, key = gm
        gm_client.emit("map_generate", {
            "room": room, "gmKey": key,
            "mapWidth": 100000, "mapHeight": 2, "discovered": False,
        })
        assert len(mudfinder.ROOMS[room].mapData["mapArray"][0]) == mudfinder.MAX_MAP_DIMENSION

    @pytest.mark.parametrize("bad", ["abc", None, 0, -4, ""])
    def test_a_size_that_is_not_a_usable_number_is_refused(self, gm, bad):
        gm_client, room, key = gm
        gm_client.emit("map_generate", {
            "room": room, "gmKey": key,
            "mapWidth": bad, "mapHeight": 4, "discovered": False,
        })
        assert mudfinder.ROOMS[room].mapData["mapArray"] == []


def join_second_gm(room, key):
    """A second GM view of the same room, as a GM with two tabs open has."""
    other = mudfinder.socketio.test_client(mudfinder.app)
    other.emit("join_gm", {"room": room, "gmKey": key})
    other.get_received()
    return other


class TestGmBroadcasts:
    """A GM with two tabs open, or two people running the game together.

    gmRoom holds the first GM's session id, and later GM views join it. Map
    events were emitted to the caller rather than to that room, so they only
    reached everyone by accident -- when the acting tab happened to be the
    first one. Any other tab acting left the rest showing a map that no longer
    existed, and clicking on it edited tiles by stale coordinates.
    """

    def test_generating_from_the_second_tab_reaches_the_first(self, gm):
        gm_client, room, key = gm
        other = join_second_gm(room, key)
        other.emit("map_generate", {
            "room": room, "gmKey": key,
            "mapWidth": 3, "mapHeight": 3, "discovered": False,
        })
        assert "gm_map" in event_names(gm_client.get_received())
        other.disconnect()

    def test_generating_from_the_first_tab_reaches_the_second(self, gm):
        gm_client, room, key = gm
        other = join_second_gm(room, key)
        gm_client.emit("map_generate", {
            "room": room, "gmKey": key,
            "mapWidth": 3, "mapHeight": 3, "discovered": False,
        })
        assert "gm_map" in event_names(other.get_received())
        other.disconnect()

    def test_resizing_from_the_second_tab_reaches_the_first(self, gm):
        gm_client, room, key = gm
        gm_client.emit("map_generate", {
            "room": room, "gmKey": key,
            "mapWidth": 3, "mapHeight": 3, "discovered": False,
        })
        gm_client.get_received()
        other = join_second_gm(room, key)
        other.emit("map_resize", {"room": room, "gmKey": key, "mapWidth": 5, "mapHeight": 5})
        assert "gm_map" in event_names(gm_client.get_received())
        other.disconnect()

    def test_a_pasted_map_from_the_second_tab_reaches_the_first(self, gm):
        gm_client, room, key = gm
        other = join_second_gm(room, key)
        other.emit("map_upload", {
            "room": room, "gmKey": key, "mapText": "F\tF\n", "discovered": False,
        })
        assert "gm_map" in event_names(gm_client.get_received())
        other.disconnect()

    def test_clearing_the_map_from_the_second_tab_reaches_the_first(self, gm):
        gm_client, room, key = gm
        other = join_second_gm(room, key)
        other.emit("clear_map", {"room": room, "gmKey": key})
        assert "gm_map" in event_names(gm_client.get_received())
        other.disconnect()

    def test_editing_a_tile_from_the_second_tab_reaches_the_first(self, gm):
        gm_client, room, key = gm
        gm_client.emit("map_generate", {
            "room": room, "gmKey": key,
            "mapWidth": 3, "mapHeight": 3, "discovered": True,
        })
        gm_client.get_received()
        other = join_second_gm(room, key)
        other.emit("map_edit", {
            "room": room, "gmKey": key,
            "tiles": [{"xCoord": 1, "yCoord": 1, "newTile": "wallTile"}],
        })
        assert "gm_map_update" in event_names(gm_client.get_received())
        other.disconnect()


PNG_PIXEL = ("data:image;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJ"
             "AAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")
OTHER_PIXEL = ("data:image;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFc"
               "SJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==")


class TestImagePruning:
    """Uploaded images live in a dict that is written into every autosave.

    Nothing ever removed an entry, so a GM trying three battlemaps carried all
    three in the save file for the rest of the game, at full size.
    """

    def test_an_uploaded_background_is_stored(self, gm):
        gm_client, room, _ = gm
        set_background(gm_client, room, PNG_PIXEL)
        assert len(mudfinder.ROOMS[room].images) == 1

    def test_replacing_a_background_drops_the_old_one(self, gm):
        gm_client, room, _ = gm
        set_background(gm_client, room, PNG_PIXEL)
        set_background(gm_client, room, OTHER_PIXEL)
        assert len(mudfinder.ROOMS[room].images) == 1

    def test_the_background_still_in_use_survives(self, gm):
        gm_client, room, _ = gm
        set_background(gm_client, room, PNG_PIXEL)
        set_background(gm_client, room, OTHER_PIXEL)
        current = mudfinder.ROOMS[room].mapData["mapBackground"]
        assert current.split("&id=")[1] in mudfinder.ROOMS[room].images

    def test_an_image_a_unit_is_wearing_is_kept(self, gm):
        """The current background is not the only thing that can hold an image,
        so pruning cannot simply keep that one and drop the rest."""
        gm_client, room, key = gm
        gm_client.emit("add_unit", {
            "room": room, "gmKey": key, "addToInitiative": False,
            "unit": {"charName": "Goblin"},
        })
        gm_client.emit("image_upload", room, PNG_PIXEL, "unitToken", "0")
        token = mudfinder.ROOMS[room].unitList[0].token
        set_background(gm_client, room, OTHER_PIXEL)
        assert token.split("&id=")[1] in mudfinder.ROOMS[room].images

    def test_an_image_a_saved_encounter_refers_to_is_kept(self, gm):
        """Saved encounters keep their own copy of mapData, so the background
        they were saved with is still wanted after the live map moves on."""
        gm_client, room, key = gm
        set_background(gm_client, room, PNG_PIXEL)
        saved_background = mudfinder.ROOMS[room].mapData["mapBackground"]
        gm_client.emit("save_encounter", {
            "room": room, "gmKey": key, "encounterName": "Ambush",
        })
        set_background(gm_client, room, OTHER_PIXEL)
        assert saved_background.split("&id=")[1] in mudfinder.ROOMS[room].images

    def test_a_linked_background_stores_nothing_to_prune(self, gm):
        """A plain URL is not an upload, so there is nothing in the dict."""
        gm_client, room, _ = gm
        set_background(gm_client, room)
        assert mudfinder.ROOMS[room].images == {}


PNG_TOKEN = ("data:image;base64, iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJ"
             "AAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")


class TestAddingSeveralCreatures:
    """Six goblins is one encounter, not six trips through the form.

    Above one copy the initiative field stops meaning the finished count --
    which six creatures cannot share -- and means the modifier each of them
    rolls a d20 against.
    """

    def add(self, gm_client, room, key, count, **overrides):
        payload = {
            "room": room, "gmKey": key, "count": count,
            "addToInitiative": True, "initiativeBonus": 0,
            "unit": {"charName": "Goblin"},
        }
        payload.update(overrides)
        gm_client.emit("add_units", payload)
        return mudfinder.ROOMS[room]

    def test_it_adds_the_requested_number(self, gm):
        gm_client, room, key = gm
        session = self.add(gm_client, room, key, 6)
        assert len(session.unitList) == 6

    def test_every_copy_is_the_creature_that_was_asked_for(self, gm):
        gm_client, room, key = gm
        session = self.add(gm_client, room, key, 3, unit={"charName": "Orc", "HP": 15})
        assert [u.charName for u in session.unitList] == ["Orc"] * 3
        assert [u.HP for u in session.unitList] == [15] * 3

    def test_the_copies_are_separate_creatures(self, gm):
        """The map and the initiative list both track units by uuid, so sharing
        one would make the copies the same creature in two places."""
        gm_client, room, key = gm
        session = self.add(gm_client, room, key, 4)
        assert len({u.uuid for u in session.unitList}) == 4

    def test_a_supplied_uuid_is_not_reused_either(self, gm):
        gm_client, room, key = gm
        session = self.add(gm_client, room, key, 3,
                           unit={"charName": "Goblin", "uuid": "template-uuid"})
        assert "template-uuid" not in {u.uuid for u in session.unitList}

    def test_they_are_numbered(self, gm):
        gm_client, room, key = gm
        session = self.add(gm_client, room, key, 4)
        assert [u.unitNum for u in session.unitList] == [0, 1, 2, 3]

    def test_each_one_rolls_its_own_initiative(self, gm):
        """Identical scores would mean one roll shared out, which is the thing
        this replaces."""
        gm_client, room, key = gm
        session = self.add(gm_client, room, key, 20, initiativeBonus=0)
        assert len({u.initiative for u in session.unitList}) > 1

    def test_the_rolls_are_a_d20_plus_the_bonus(self, gm):
        gm_client, room, key = gm
        session = self.add(gm_client, room, key, 40, initiativeBonus=5)
        assert all(6 <= u.initiative <= 25 for u in session.unitList)

    def test_a_bonus_typed_with_a_sign_is_understood(self, gm):
        gm_client, room, key = gm
        session = self.add(gm_client, room, key, 40, initiativeBonus="+5")
        assert all(6 <= u.initiative <= 25 for u in session.unitList)

    def test_a_negative_bonus_is_understood(self, gm):
        gm_client, room, key = gm
        session = self.add(gm_client, room, key, 40, initiativeBonus="-2")
        assert all(-1 <= u.initiative <= 18 for u in session.unitList)

    @pytest.mark.parametrize("bad", ["", None, "abc", "+"])
    def test_an_unreadable_bonus_counts_as_none(self, gm, bad):
        gm_client, room, key = gm
        session = self.add(gm_client, room, key, 40, initiativeBonus=bad)
        assert all(1 <= u.initiative <= 20 for u in session.unitList)

    def test_they_go_into_the_order_by_their_rolls(self, gm):
        gm_client, room, key = gm
        session = self.add(gm_client, room, key, 8, initiativeBonus=3)
        rolled = [int(u.initiative) for u in session.initiativeList]
        assert len(rolled) == 8
        assert rolled == sorted(rolled, reverse=True)

    def test_they_can_be_added_without_joining_the_order(self, gm):
        gm_client, room, key = gm
        session = self.add(gm_client, room, key, 5, addToInitiative=False)
        assert session.initiativeList == []
        assert len(session.unitList) == 5

    def test_a_single_copy_still_takes_an_exact_initiative(self, gm):
        """A GM adding one creature often already knows where it goes, so the
        field keeps the meaning it has always had below two copies."""
        gm_client, room, key = gm
        session = self.add(gm_client, room, key, 1,
                           unit={"charName": "Boss", "initiative": "17"})
        assert session.unitList[0].initiative == "17"

    def test_wrong_key_cannot_add(self, gm):
        gm_client, room, _ = gm
        gm_client.emit("add_units", {
            "room": room, "gmKey": "wrong", "count": 3, "addToInitiative": False,
            "initiativeBonus": 0, "unit": {"charName": "Goblin"},
        })
        assert mudfinder.ROOMS[room].unitList == []

    def test_unknown_room_is_ignored(self, client):
        client.emit("add_units", {
            "room": "no-such-room", "gmKey": GM_KEY, "count": 3,
            "addToInitiative": False, "initiativeBonus": 0,
            "unit": {"charName": "Goblin"},
        })
        assert client.get_received() == []

    @pytest.mark.parametrize("bad", ["abc", None, 0, -3, ""])
    def test_a_count_that_is_not_a_usable_number_is_refused(self, gm, bad):
        gm_client, room, key = gm
        session = self.add(gm_client, room, key, bad)
        assert session.unitList == []

    def test_an_absurd_count_is_clamped(self, gm):
        """Every copy is a Unit that then goes into every autosave, so a
        slipped keypress cannot be taken at face value."""
        gm_client, room, key = gm
        session = self.add(gm_client, room, key, 100000)
        assert len(session.unitList) == mudfinder.MAX_UNITS_PER_ADD


class TestSharingATokenAcrossCopies:
    """The token is chosen once for the batch and uploaded with it.

    It cannot be stored when the GM picks it, because the creatures it belongs
    to do not exist yet and prune_unused_images removes exactly that: an image
    nothing points at.
    """

    def add(self, gm_client, room, key, count, token):
        gm_client.emit("add_units", {
            "room": room, "gmKey": key, "count": count, "addToInitiative": False,
            "initiativeBonus": 0, "unit": {"charName": "Goblin", "token": token},
        })
        return mudfinder.ROOMS[room]

    def test_an_uploaded_token_is_stored(self, gm):
        gm_client, room, key = gm
        session = self.add(gm_client, room, key, 6, PNG_TOKEN)
        assert len(session.images) == 1

    def test_every_copy_wears_it(self, gm):
        gm_client, room, key = gm
        session = self.add(gm_client, room, key, 6, PNG_TOKEN)
        stored = "get_image.html?room=%s&id=%s" % (room, list(session.images)[0])
        assert [u.token for u in session.unitList] == [stored] * 6

    def test_they_share_one_copy_of_it(self, gm):
        """Six creatures holding six identical images would go into every
        autosave six times."""
        gm_client, room, key = gm
        session = self.add(gm_client, room, key, 6, PNG_TOKEN)
        assert len(session.images) == 1

    def test_it_survives_the_next_prune(self, gm):
        """Which is what storing it at the picker would not have done."""
        gm_client, room, key = gm
        session = self.add(gm_client, room, key, 3, PNG_TOKEN)
        token_id = list(session.images)[0]
        gm_client.emit("image_upload", room, "https://example.invalid/map.png",
                       "mapBackground", "")
        assert token_id in session.images

    def test_a_linked_token_is_passed_through_untouched(self, gm):
        gm_client, room, key = gm
        link = "https://example.invalid/goblin.png"
        session = self.add(gm_client, room, key, 3, link)
        assert [u.token for u in session.unitList] == [link] * 3
        assert session.images == {}

    def test_no_token_is_no_token(self, gm):
        gm_client, room, key = gm
        session = self.add(gm_client, room, key, 3, "")
        assert [u.token for u in session.unitList] == [""] * 3


@pytest.fixture
def browser_style_game(client):
    """A game whose GM room is genuinely separate from its player room.

    A room is named after the socket that created it, and gmRoom is the socket
    of the first GM to join. The conftest gm fixture does both from one client,
    so those two names are the same string there and a GM-only emit reaches
    everybody. In a browser they are never the same: the lobby page creates the
    game and gm.html loads as a fresh connection. Anything asserting that a
    message stopped at the GM has to be set up the way a browser sets it up, or
    it is asserting nothing.

    Returns (gm_client, room, gmKey).
    """
    client.emit("create", {"name": "Test Game", "gmKey": GM_KEY})
    room = event(client.get_received(), "create_room")["args"][0]["room"]
    gm_client = join_gm_socket(room)
    assert mudfinder.ROOMS[room].gmRoom != room
    yield gm_client, room, GM_KEY
    if gm_client.is_connected():
        gm_client.disconnect()


def join_gm_socket(room, key=GM_KEY):
    """A GM view on its own socket, as gm.html is."""
    gm_client = mudfinder.socketio.test_client(mudfinder.app)
    gm_client.emit("join_gm", {"room": room, "gmKey": key})
    gm_client.get_received()
    return gm_client


class TestInitiativeRollsAreTheGMs:
    """The rolls are reported so the GM can see what the numbers came from.

    Which creature rolled a 3 is not something the party gets to know, so the
    report goes to the GM's views and no further.
    """

    def test_the_gm_is_told_what_was_rolled(self, browser_style_game):
        gm_client, room, key = browser_style_game
        gm_client.emit("add_units", {
            "room": room, "gmKey": key, "count": 3, "addToInitiative": True,
            "initiativeBonus": 2, "unit": {"charName": "Goblin"},
        })
        chat = event(gm_client.get_received(), "chat")["args"][0]["chat"]
        assert chat.startswith("Goblin initiative: ")
        assert chat.count("d20(") == 3

    def test_the_report_shows_the_die_the_bonus_and_the_total(self, browser_style_game):
        gm_client, room, key = browser_style_game
        gm_client.emit("add_units", {
            "room": room, "gmKey": key, "count": 100, "addToInitiative": False,
            "initiativeBonus": 4, "unit": {"charName": "Goblin"},
        })
        chat = event(gm_client.get_received(), "chat")["args"][0]["chat"]
        rolls = chat.split(": ", 1)[1].split(", ")
        assert len(rolls) == 100
        assert all(re.fullmatch(r"d20\((\d+)\)\+4 = (\d+)", roll) for roll in rolls)

    def test_the_players_are_not_told(self, browser_style_game):
        gm_client, room, key = browser_style_game
        player = mudfinder.socketio.test_client(mudfinder.app)
        player.emit("player_join", {"room": room, "charName": "Aria"})
        player.get_received()
        gm_client.emit("add_units", {
            "room": room, "gmKey": key, "count": 3, "addToInitiative": True,
            "initiativeBonus": 2, "unit": {"charName": "Goblin"},
        })
        assert "chat" not in event_names(player.get_received())

    def test_a_second_gm_view_is_told(self, browser_style_game):
        gm_client, room, key = browser_style_game
        second = join_gm_socket(room, key)
        second.emit("add_units", {
            "room": room, "gmKey": key, "count": 2, "addToInitiative": True,
            "initiativeBonus": 0, "unit": {"charName": "Goblin"},
        })
        assert "chat" in event_names(gm_client.get_received())

    def test_a_single_creature_is_not_reported(self, browser_style_game):
        """Nothing was rolled, so there is nothing to report."""
        gm_client, room, key = browser_style_game
        gm_client.emit("add_units", {
            "room": room, "gmKey": key, "count": 1, "addToInitiative": True,
            "initiativeBonus": 0, "unit": {"charName": "Boss", "initiative": "17"},
        })
        assert "chat" not in event_names(gm_client.get_received())


class TestPaintingLight:
    """Pathfinder light levels, painted a square at a time.

    Pathfinder keeps bright and normal apart where 5e folds them together,
    because they drive different rules -- dim light gives concealment, darkness
    blinds anyone without darkvision, bright light dazzles the light-sensitive.
    So there are four levels to paint, and normal is the one every square
    starts as.
    """

    def mapped(self, gm_client, room, key, width=4, height=3, discovered=True):
        gm_client.emit("map_generate", {
            "room": room, "gmKey": key,
            "mapWidth": width, "mapHeight": height, "discovered": discovered,
        })
        gm_client.get_received()
        return mudfinder.ROOMS[room]

    def paint(self, gm_client, room, key, tool, *squares):
        gm_client.emit("map_edit", {
            "room": room, "gmKey": key,
            "tiles": [{"newTile": tool, "xCoord": x, "yCoord": y} for x, y in squares],
        })

    def test_a_new_map_is_lit(self, gm):
        """Normal light is the absence of the key, so a fresh square carries
        nothing at all -- which is also what makes every map that existed
        before this feature a fully lit one."""
        gm_client, room, key = gm
        session = self.mapped(gm_client, room, key)
        assert "light" not in session.mapData["mapArray"][0][0]

    @pytest.mark.parametrize("tool,level", [
        ("lightBright", "bright"),
        ("lightDim", "dim"),
        ("lightDarkness", "darkness"),
    ])
    def test_painting_a_level(self, gm, tool, level):
        gm_client, room, key = gm
        session = self.mapped(gm_client, room, key)
        self.paint(gm_client, room, key, tool, (1, 1))
        assert session.mapData["mapArray"][1][1]["light"] == level

    def test_painting_normal_removes_the_key(self, gm):
        """Rather than storing "normal", so that there is exactly one way to
        spell an unlit square."""
        gm_client, room, key = gm
        session = self.mapped(gm_client, room, key)
        self.paint(gm_client, room, key, "lightDim", (1, 1))
        self.paint(gm_client, room, key, "lightNormal", (1, 1))
        assert "light" not in session.mapData["mapArray"][1][1]

    def test_painting_normal_over_nothing_is_harmless(self, gm):
        gm_client, room, key = gm
        session = self.mapped(gm_client, room, key)
        self.paint(gm_client, room, key, "lightNormal", (1, 1))
        assert "light" not in session.mapData["mapArray"][1][1]

    def test_a_level_can_be_changed(self, gm):
        gm_client, room, key = gm
        session = self.mapped(gm_client, room, key)
        self.paint(gm_client, room, key, "lightDim", (1, 1))
        self.paint(gm_client, room, key, "lightBright", (1, 1))
        assert session.mapData["mapArray"][1][1]["light"] == "bright"

    def test_a_marquee_paints_every_square_in_it(self, gm):
        gm_client, room, key = gm
        session = self.mapped(gm_client, room, key)
        self.paint(gm_client, room, key, "lightDarkness", (0, 2), (1, 2), (2, 2), (3, 2))
        assert [tile.get("light") for tile in session.mapData["mapArray"][2]] == ["darkness"] * 4

    def test_an_unrecognised_level_is_ignored(self, gm):
        gm_client, room, key = gm
        session = self.mapped(gm_client, room, key)
        self.paint(gm_client, room, key, "lightPuce", (1, 1))
        assert "light" not in session.mapData["mapArray"][1][1]

    def test_light_leaves_the_tile_type_alone(self, gm):
        gm_client, room, key = gm
        session = self.mapped(gm_client, room, key)
        self.paint(gm_client, room, key, "wallTile", (1, 1))
        self.paint(gm_client, room, key, "lightDim", (1, 1))
        tile = session.mapData["mapArray"][1][1]
        assert (tile["tile"], tile["walkable"], tile["light"]) == ("wallTile", False, "dim")

    def test_the_tile_type_leaves_light_alone(self, gm):
        gm_client, room, key = gm
        session = self.mapped(gm_client, room, key)
        self.paint(gm_client, room, key, "lightDim", (1, 1))
        self.paint(gm_client, room, key, "wallTile", (1, 1))
        assert session.mapData["mapArray"][1][1]["light"] == "dim"

    @pytest.mark.parametrize("tool,expected", [
        ("wallTile", "wallTile"),
        ("floorTile", "floorTile"),
        ("stairsUp", "stairsUp"),
    ])
    def test_the_other_tools_still_dispatch(self, gm, tool, expected):
        """map_edit dispatches on substrings of newTile, so a light branch in
        front of that chain could swallow the tools that follow it."""
        gm_client, room, key = gm
        session = self.mapped(gm_client, room, key)
        self.paint(gm_client, room, key, tool, (1, 1))
        assert session.mapData["mapArray"][1][1]["tile"] == expected

    def test_the_secret_toggle_still_works(self, gm):
        gm_client, room, key = gm
        session = self.mapped(gm_client, room, key)
        self.paint(gm_client, room, key, "secret", (1, 1))
        assert session.mapData["mapArray"][1][1]["secret"] is True

    def test_light_survives_a_resize(self, gm):
        gm_client, room, key = gm
        session = self.mapped(gm_client, room, key)
        self.paint(gm_client, room, key, "lightDim", (1, 1))
        gm_client.emit("map_resize", {"room": room, "gmKey": key, "mapWidth": 8, "mapHeight": 6})
        assert session.mapData["mapArray"][1][1]["light"] == "dim"

    def test_light_rides_along_into_a_saved_encounter(self, gm):
        gm_client, room, key = gm
        session = self.mapped(gm_client, room, key)
        self.paint(gm_client, room, key, "lightDarkness", (1, 1))
        gm_client.emit("save_encounter", {
            "room": room, "gmKey": key, "encounterName": "The Cavern"})
        saved = session.savedEncounters["The Cavern"]["mapData"]["mapArray"]
        assert saved[1][1]["light"] == "darkness"

    def test_generating_a_new_map_starts_lit_again(self, gm):
        gm_client, room, key = gm
        session = self.mapped(gm_client, room, key)
        self.paint(gm_client, room, key, "lightDarkness", (1, 1))
        self.mapped(gm_client, room, key)
        assert all("light" not in tile for row in session.mapData["mapArray"] for tile in row)

    def test_the_gm_is_sent_the_change(self, gm):
        gm_client, room, key = gm
        self.mapped(gm_client, room, key)
        self.paint(gm_client, room, key, "lightDim", (1, 1))
        updated = event(gm_client.get_received(), "gm_map_update")["args"][0]["mapArray"]
        assert [tile["light"] for tile in updated] == ["dim"]

    def test_wrong_key_cannot_paint(self, gm):
        gm_client, room, key = gm
        session = self.mapped(gm_client, room, key)
        gm_client.emit("map_edit", {
            "room": room, "gmKey": "wrong",
            "tiles": [{"newTile": "lightDim", "xCoord": 1, "yCoord": 1}],
        })
        assert "light" not in session.mapData["mapArray"][1][1]

    def test_unknown_room_is_ignored(self, client):
        client.emit("map_edit", {
            "room": "no-such-room", "gmKey": GM_KEY,
            "tiles": [{"newTile": "lightDim", "xCoord": 0, "yCoord": 0}],
        })
        assert client.get_received() == []


class TestLightAndTheFogOfWar:
    """What the players are told about light, and what they are not.

    A light level on a square nobody has explored would draw the shape of the
    room through the fog, which is the whole thing the fog is for.
    """

    def lit_map(self, gm_client, room, key):
        gm_client.emit("map_generate", {
            "room": room, "gmKey": key,
            "mapWidth": 4, "mapHeight": 3, "discovered": False,
        })
        gm_client.get_received()
        session = mudfinder.ROOMS[room]
        for x, y in [(0, 0), (1, 1), (2, 2)]:
            session.mapData["mapArray"][y][x]["seen"] = True
        return session

    def paint(self, gm_client, room, key, tool, x, y):
        gm_client.emit("map_edit", {
            "room": room, "gmKey": key,
            "tiles": [{"newTile": tool, "xCoord": x, "yCoord": y}],
        })

    def test_a_seen_square_carries_its_light(self, gm):
        gm_client, room, key = gm
        session = self.lit_map(gm_client, room, key)
        session.mapData["mapArray"][0][0]["light"] = "dim"
        assert session.player_map()["mapArray"][0][0]["light"] == "dim"

    def test_an_unseen_square_carries_none(self, gm):
        gm_client, room, key = gm
        session = self.lit_map(gm_client, room, key)
        session.mapData["mapArray"][0][3]["light"] = "darkness"
        assert "light" not in session.player_map()["mapArray"][0][3]

    def test_a_secret_door_is_lit_like_the_wall_it_pretends_to_be(self, gm):
        """The masking replaces it with a plain wall. The one un-dimmed square
        in a dim wall would be a tell."""
        gm_client, room, key = gm
        session = self.lit_map(gm_client, room, key)
        tile = session.mapData["mapArray"][1][1]
        tile["secret"] = True
        tile["light"] = "dim"
        masked = session.player_map()["mapArray"][1][1]
        assert masked["tile"] == "wallTile"
        assert masked["light"] == "dim"

    def test_a_live_paint_reaches_the_players(self, gm):
        gm_client, room, key = gm
        self.lit_map(gm_client, room, key)
        player = mudfinder.socketio.test_client(mudfinder.app)
        player.emit("player_join", {"room": room, "charName": "Aria"})
        player.get_received()
        self.paint(gm_client, room, key, "lightDim", 0, 0)
        updated = event(player.get_received(), "player_map_update")["args"][0]["mapArray"]
        assert [tile["light"] for tile in updated] == ["dim"]

    def test_a_live_paint_on_an_unseen_square_does_not(self, gm):
        """This mask edits the tile in place rather than rebuilding it, so
        anything not explicitly removed reaches the players untouched."""
        gm_client, room, key = gm
        self.lit_map(gm_client, room, key)
        player = mudfinder.socketio.test_client(mudfinder.app)
        player.emit("player_join", {"room": room, "charName": "Aria"})
        player.get_received()
        self.paint(gm_client, room, key, "lightDarkness", 3, 0)
        updated = event(player.get_received(), "player_map_update")["args"][0]["mapArray"]
        assert updated[0]["tile"] == "unseenTile"
        assert "light" not in updated[0]

    def test_the_gm_sees_what_the_players_do_not(self, gm):
        """The contrast, so the two cannot quietly converge."""
        gm_client, room, key = gm
        self.lit_map(gm_client, room, key)
        self.paint(gm_client, room, key, "lightDarkness", 3, 0)
        updated = event(gm_client.get_received(), "gm_map_update")["args"][0]["mapArray"]
        assert updated[0]["light"] == "darkness"

    def test_discovering_a_square_hands_over_its_light(self, gm):
        """Painted while unexplored, revealed later -- the level was on the
        server the whole time and arrives with the reveal."""
        gm_client, room, key = gm
        session = self.lit_map(gm_client, room, key)
        session.mapData["mapArray"][0][3]["light"] = "darkness"
        assert "light" not in session.player_map()["mapArray"][0][3]
        session.mapData["mapArray"][0][3]["seen"] = True
        assert session.player_map()["mapArray"][0][3]["light"] == "darkness"


class TestUpdatingVision:
    def add_goblin(self, gm_client, room, key):
        gm_client.emit("add_unit", {
            "room": room, "gmKey": key, "addToInitiative": False,
            "unit": {"charName": "Goblin"},
        })
        gm_client.get_received()
        return mudfinder.ROOMS[room].unitList[0]

    def update(self, gm_client, room, key, **fields):
        payload = {"room": room, "gmKey": key, "unitNum": 0}
        payload.update(fields)
        gm_client.emit("update_unit", payload)

    def test_the_gm_can_give_a_creature_darkvision(self, gm):
        gm_client, room, key = gm
        goblin = self.add_goblin(gm_client, room, key)
        self.update(gm_client, room, key, darkvision=True, lowLight=True)
        assert (goblin.darkvision, goblin.lowLight) == (True, True)

    def test_the_setting_reaches_the_gm_view(self, gm):
        """It is to_json that carries this, and the field used to be missing
        from it -- so the checkbox reverted on the next update."""
        gm_client, room, key = gm
        self.add_goblin(gm_client, room, key)
        self.update(gm_client, room, key, darkvision=True)
        state = event(gm_client.get_received(), "gm_update")["args"][0]
        assert state["unitList"][0]["darkvision"] is True

    def test_an_update_that_omits_a_field_leaves_it_alone(self, gm):
        """A tab opened before a field was added to the sheet should not be
        able to take the handler down, or silently blank the value."""
        gm_client, room, key = gm
        goblin = self.add_goblin(gm_client, room, key)
        self.update(gm_client, room, key, darkvision=True)
        self.update(gm_client, room, key, color="red")
        assert goblin.darkvision is True
        assert goblin.color == "red"
