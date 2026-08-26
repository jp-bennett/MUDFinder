"""Tests for the Socket.IO event handlers.

This is the layer that broke silently when the server-side Socket.IO libraries
drifted ahead of the vendored 2.x browser client, so it is worth keeping
covered: if a dependency bump breaks the wire protocol or the handler
signatures, these fail rather than the app merely failing to work in a browser.
"""

import json
import re
import sqlite3

import pytest

import mudfinder
from helpers import GM_KEY, event, event_names
from session import Session
from unit import Unit


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


class TestCreatureSearch:
    """Finding a monster in a table of ten thousand.

    The picker searches by name, CR and type in any combination. The columns it
    gets back are deliberately few: the handler this replaced selected every
    one of the hundred, which was three megabytes for CR 2 alone.
    """

    def search(self, client, **criteria):
        return client.emit("database_creature_search", criteria, callback=True)

    def test_search_by_name(self, client):
        result = self.search(client, name="dire ape")
        assert "Dire Ape" in [c["Name"] for c in result["creatures"]]

    def test_the_name_search_is_a_substring(self, client):
        names = [c["Name"] for c in self.search(client, name="dire ape")["creatures"]]
        assert "Fiendish Dire Ape" in names

    def test_search_by_cr(self, client):
        result = self.search(client, cr="3")
        assert result["creatures"]
        assert all(c["CR"] == "3" for c in result["creatures"])

    def test_search_by_type(self, client):
        result = self.search(client, type="dragon")
        assert result["creatures"]
        assert all(c["TypeNorm"] == "dragon" for c in result["creatures"])

    def test_a_type_filter_is_exact(self, client):
        """TypeNorm is matched, not the free-text Type, so asking for humanoids
        does not also hand back every monstrous humanoid."""
        result = self.search(client, type="humanoid")
        assert all(c["TypeNorm"] == "humanoid" for c in result["creatures"])

    def test_all_three_together(self, client):
        result = self.search(client, name="goblin", cr="1/3", type="humanoid")
        assert result["creatures"]
        for creature in result["creatures"]:
            assert "goblin" in creature["Name"].lower()
            assert creature["CR"] == "1/3"
            assert creature["TypeNorm"] == "humanoid"

    def test_an_empty_search_returns_nothing(self, client):
        """Not a request for the whole table."""
        assert self.search(client)["creatures"] == []

    def test_an_unknown_type_returns_nothing(self, client):
        assert self.search(client, type="sasquatch")["creatures"] == []

    def test_no_match_returns_nothing(self, client):
        assert self.search(client, name="zzzznotacreature")["creatures"] == []

    def test_a_broad_search_is_capped_and_says_so(self, client):
        result = self.search(client, type="humanoid")
        assert len(result["creatures"]) == mudfinder.MAX_CREATURE_RESULTS
        assert result["truncated"] is True

    def test_a_narrow_search_is_not_marked_truncated(self, client):
        assert self.search(client, name="dire ape")["truncated"] is False

    @pytest.mark.parametrize("wildcard", ["%", "_", "%%", "a_e"])
    def test_like_wildcards_are_not_wildcards(self, client, wildcard):
        """A GM typing % was matching every creature in the table."""
        names = [c["Name"] for c in self.search(client, name=wildcard)["creatures"]]
        assert all(wildcard.replace("\\", "") in name.lower() or not names
                   for name in [n.lower() for n in names])

    def test_a_percent_search_does_not_return_the_table(self, client):
        assert self.search(client, name="%")["creatures"] == []

    def test_only_the_list_columns_come_back(self, client):
        """A regression here is measured in megabytes, not fields."""
        creature = self.search(client, name="dire ape")["creatures"][0]
        assert set(creature) == {"id", "Name", "CR", "Type", "TypeNorm", "Size",
                                 "HP", "Init", "Source"}

    def test_the_dropped_column_is_in_no_response(self, client):
        creature = self.search(client, name="dire ape")["creatures"][0]
        assert "FullText" not in creature

    def test_the_response_stays_small(self, client):
        """The broadest search there is, still well under a megabyte."""
        result = self.search(client, type="humanoid")
        assert len(json.dumps(result)) < 200000

    def test_both_datasets_are_reachable(self, client):
        """One creature from the bundled bestiary and one from the imported
        adventure statblocks, so a merge that dropped either would fail here."""
        assert self.search(client, name="Dire Ape")["creatures"]
        assert self.search(client, name="Bridge Guard")["creatures"]

    def test_the_type_list_matches_the_import(self, client):
        """The filter can only offer what the import wrote into TypeNorm."""
        import tools.import_creatures as importer
        assert sorted(mudfinder.CREATURE_TYPES) == sorted(importer.CREATURE_TYPES)


class TestFetchingOneCreature:
    def creature_id(self, client, name):
        return client.emit("database_creature_search", {"name": name},
                           callback=True)["creatures"][0]["id"]

    def test_it_returns_the_creature_and_a_unit(self, client):
        got = client.emit("database_creature", self.creature_id(client, "Dire Ape"),
                          callback=True)
        assert got["creature"]["Name"] == "Dire Ape"
        assert got["unit"]["charName"] == "Dire Ape"

    def test_it_returns_the_initiative_bonus_separately(self, client):
        """The unit carries no initiative: what a statblock gives is a modifier
        to roll against, and the server rolls it per copy."""
        got = client.emit("database_creature", self.creature_id(client, "Dire Ape"),
                          callback=True)
        assert got["initiativeBonus"] == 2
        assert "initiative" not in got["unit"]

    def test_an_unknown_id_returns_nothing(self, client):
        # The handler returns None; the test client reports "no callback data"
        # as an empty list, as it does for request_images.
        assert not client.emit("database_creature", 99999999, callback=True)

    @pytest.mark.parametrize("bad", ["abc", None, "", "1; drop table creatures--"])
    def test_a_bad_id_is_refused_rather_than_raising(self, client, bad):
        assert not client.emit("database_creature", bad, callback=True)

    def test_the_creatures_table_survives_a_hostile_id(self, client):
        client.emit("database_creature", "1; drop table creatures--", callback=True)
        assert client.emit("database_creature_search", {"name": "Dire Ape"},
                           callback=True)["creatures"]


class TestAddingMonstersFromTheDatabase:
    """The flow the picker drives: pick a creature, say how many, and let the
    server roll each one's initiative."""

    def add(self, gm_client, room, key, unit, count, bonus, roll=True):
        gm_client.emit("add_units", {
            "room": room, "gmKey": key, "count": count, "addToInitiative": True,
            "initiativeBonus": bonus, "rollInitiative": roll, "unit": unit,
        })
        return mudfinder.ROOMS[room]

    def dire_ape(self, client):
        creature_id = client.emit("database_creature_search", {"name": "Dire Ape"},
                                  callback=True)["creatures"][0]["id"]
        return client.emit("database_creature", creature_id, callback=True)

    def test_seven_of_them(self, gm):
        gm_client, room, key = gm
        ape = self.dire_ape(gm_client)
        session = self.add(gm_client, room, key, ape["unit"], 7, ape["initiativeBonus"])
        assert len([u for u in session.unitList if u.charName == "Dire Ape"]) == 7

    def test_each_rolls_its_own_initiative(self, gm):
        gm_client, room, key = gm
        ape = self.dire_ape(gm_client)
        session = self.add(gm_client, room, key, ape["unit"], 20, ape["initiativeBonus"])
        assert len({u.initiative for u in session.unitList}) > 1

    def test_the_rolls_use_the_creatures_own_bonus(self, gm):
        gm_client, room, key = gm
        ape = self.dire_ape(gm_client)
        session = self.add(gm_client, room, key, ape["unit"], 30, ape["initiativeBonus"])
        assert all(3 <= int(u.initiative) <= 22 for u in session.unitList)

    def test_the_statblock_rides_along(self, gm):
        gm_client, room, key = gm
        ape = self.dire_ape(gm_client)
        session = self.add(gm_client, room, key, ape["unit"], 3, ape["initiativeBonus"])
        goblin = session.unitList[0]
        assert (goblin.HP, goblin.size, goblin.lowLight) == (30, "large", True)

    def test_a_single_monster_still_rolls(self, gm):
        """Its Init is a modifier, so taking it as a finished count would put a
        Dire Ape at initiative 2 every time."""
        gm_client, room, key = gm
        ape = self.dire_ape(gm_client)
        rolled = set()
        for _ in range(20):
            mudfinder.ROOMS[room].unitList = []
            session = self.add(gm_client, room, key, ape["unit"], 1, ape["initiativeBonus"])
            rolled.add(int(session.unitList[0].initiative))
        assert len(rolled) > 1

    def test_hand_typed_adds_are_unchanged(self, gm):
        """Without the flag, one creature still means an exact count."""
        gm_client, room, key = gm
        gm_client.emit("add_units", {
            "room": room, "gmKey": key, "count": 1, "addToInitiative": False,
            "initiativeBonus": 0, "unit": {"charName": "Boss", "initiative": "17"},
        })
        assert mudfinder.ROOMS[room].unitList[0].initiative == "17"


class TestSortingTheCreatureList:
    """The picker's column headings.

    Sorted in the query rather than in the browser, because the result is
    capped: re-ordering the three hundred rows already sent would give the
    first three hundred by name rearranged, which is not the same as the three
    hundred lowest-CR creatures.
    """

    def search(self, client, **criteria):
        criteria.setdefault("name", "dragon")
        return client.emit("database_creature_search", criteria,
                           callback=True)["creatures"]

    def column(self, client, field, **criteria):
        return [c[field] for c in self.search(client, **criteria)]

    def test_the_default_is_by_name(self, client):
        names = self.column(client, "Name")
        assert names == sorted(names, key=str.lower)

    def test_by_name_reversed(self, client):
        names = self.column(client, "Name", sort="Name", descending=True)
        assert names == sorted(names, key=str.lower, reverse=True)

    def test_by_cr_is_numeric_not_alphabetical(self, client):
        """Sorted as the text it is stored as, 10 comes before 2 and the
        fractions land somewhere among the twenties."""
        crs = [float(c) for c in self.column(client, "CR", sort="CR") if "/" not in c]
        assert crs == sorted(crs)

    def test_by_cr_puts_the_fractions_first(self, client):
        crs = self.column(client, "CR", name="goblin", sort="CR")
        assert crs[0] in ("1/8", "1/6", "1/4", "1/3", "1/2")

    def test_by_cr_reversed(self, client):
        crs = [float(c) for c in self.column(client, "CR", sort="CR", descending=True)
               if "/" not in c]
        assert crs == sorted(crs, reverse=True)

    def test_a_creature_with_no_cr_sorts_to_the_end(self, client):
        crs = self.column(client, "CR", name="fiendish", sort="CR")
        if "-" in crs:
            assert crs.index("-") == len(crs) - crs.count("-")

    def test_by_hp_is_numeric(self, client):
        hp = [float(h) for h in self.column(client, "HP", sort="HP") if h and h[0].isdigit()]
        assert hp == sorted(hp)

    def test_by_size_follows_the_scale(self, client):
        """Not the alphabet, which starts at Colossal and ends at Tiny."""
        order = ["Fine", "Diminutive", "Tiny", "Small", "Medium", "Large",
                 "Huge", "Gargantuan", "Colossal"]
        sizes = [order.index(s) for s in self.column(client, "Size", sort="Size") if s in order]
        assert sizes == sorted(sizes)

    def test_by_size_reversed_starts_at_the_biggest(self, client):
        sizes = self.column(client, "Size", sort="Size", descending=True)
        assert sizes[0] in ("Colossal", "Gargantuan", "Huge")

    def test_by_type(self, client):
        types = self.column(client, "TypeNorm", name="goblin", sort="TypeNorm")
        assert types == sorted(types, key=str.lower)

    def test_by_source(self, client):
        sources = self.column(client, "Source", sort="Source")
        assert sources == sorted(sources, key=str.lower)

    def test_ties_break_on_the_name(self, client):
        """So sorting by CR gives an order that can be read down rather than
        one that reshuffles every time the same query is run."""
        first = [c["Name"] for c in self.search(client, sort="CR")]
        again = [c["Name"] for c in self.search(client, sort="CR")]
        assert first == again

    def numeric_cr(self, cr):
        if "/" in cr:
            top, bottom = cr.split("/")
            return float(top) / float(bottom)
        return float(cr) if cr != "-" else 1000.0

    def test_sorting_picks_from_the_whole_match_not_the_first_page(self, client):
        """The capped list has to be the lowest-CR three hundred, not the
        alphabetical three hundred put into CR order. "a" matches far more
        creatures than the cap, so the two orderings see different rows."""
        lowest = [self.numeric_cr(c) for c in self.column(client, "CR", name="a", sort="CR")]
        by_name = [self.numeric_cr(c) for c in self.column(client, "CR", name="a")]
        assert max(lowest) < max(by_name)

    @pytest.mark.parametrize("bad", [
        "Nonsense", "", None, "Name; drop table creatures--", "CR) --", 7,
    ])
    def test_an_unusable_sort_falls_back_to_the_name(self, client, bad):
        """A sort key cannot be a bound parameter, so it is checked against our
        own list the way the spell columns are."""
        names = self.column(client, "Name", sort=bad)
        assert names == sorted(names, key=str.lower)

    def test_the_creatures_table_survives_a_hostile_sort(self, client):
        self.search(client, sort="Name; drop table creatures--")
        assert self.search(client, name="Dire Ape")

    def test_every_column_the_picker_shows_can_be_sorted_on(self, client):
        """The headings are built from the same list, so a column with no sort
        would be a heading that does nothing when clicked."""
        listed = {"Name", "CR", "TypeNorm", "Size", "HP", "Source"}
        assert listed <= set(mudfinder.CREATURE_SORTS)

class TestAlignmentStamping:
    """Every alignment write is stamped so a client can order two payloads.

    Without it a client can only ask "do I have a change outstanding", which
    says nothing about a whole map sent in answer to an earlier grid resize --
    the payload that actually undid a GM's drag.
    """

    def battlemap(self, gm_client, room, key, width=6, height=5):
        set_background(gm_client, room)
        gm_client.emit("map_generate_over_background", {
            "room": room, "gmKey": key,
            "mapWidth": width, "mapHeight": height, "discovered": False,
        })
        gm_client.get_received()
        return mudfinder.ROOMS[room]

    def align(self, gm_client, room, key, tiles_wide=12.0, x=0.0, y=0.0):
        gm_client.emit("set_background_alignment", {
            "room": room, "gmKey": key, "backgroundTilesWide": tiles_wide,
            "backgroundOffsetX": x, "backgroundOffsetY": y,
        })

    def seq(self, session):
        return session.mapData.get(mudfinder.BACKGROUND_ALIGNMENT_SEQ)

    def test_building_over_a_background_stamps_it(self, gm):
        gm_client, room, key = gm
        session = self.battlemap(gm_client, room, key)
        assert self.seq(session) == 1

    def test_every_alignment_change_raises_it(self, gm):
        gm_client, room, key = gm
        session = self.battlemap(gm_client, room, key)
        stamps = []
        for tiles_wide in [10.0, 11.0, 12.0]:
            self.align(gm_client, room, key, tiles_wide)
            stamps.append(self.seq(session))
        assert stamps == sorted(set(stamps)) and len(stamps) == 3

    def test_the_change_is_sent_with_its_stamp(self, gm):
        gm_client, room, key = gm
        session = self.battlemap(gm_client, room, key)
        self.align(gm_client, room, key, 12.4)
        update = event(gm_client.get_received(), "gm_map_update")["args"][0]
        assert update[mudfinder.BACKGROUND_ALIGNMENT_SEQ] == self.seq(session)

    def test_the_players_are_sent_it_too(self, gm):
        gm_client, room, key = gm
        self.battlemap(gm_client, room, key)
        player = mudfinder.socketio.test_client(mudfinder.app)
        player.emit("player_join", {"room": room, "charName": "Aria"})
        player.get_received()
        self.align(gm_client, room, key, 12.4)
        update = event(player.get_received(), "player_map_update")["args"][0]
        assert mudfinder.BACKGROUND_ALIGNMENT_SEQ in update

    def test_resizing_the_grid_does_not_raise_it(self, gm):
        """The whole point. A resize says nothing about the alignment, so the
        map it answers with must not look newer than the GM's last drag."""
        gm_client, room, key = gm
        session = self.battlemap(gm_client, room, key)
        self.align(gm_client, room, key, 12.4)
        before = self.seq(session)
        gm_client.emit("map_resize", {"room": room, "gmKey": key, "mapWidth": 9, "mapHeight": 7})
        assert self.seq(session) == before

    def test_the_map_a_resize_answers_with_carries_the_old_stamp(self, gm):
        gm_client, room, key = gm
        session = self.battlemap(gm_client, room, key)
        self.align(gm_client, room, key, 12.4)
        before = self.seq(session)
        gm_client.get_received()
        gm_client.emit("map_resize", {"room": room, "gmKey": key, "mapWidth": 9, "mapHeight": 7})
        sent = event(gm_client.get_received(), "gm_map")["args"][0]
        assert sent[mudfinder.BACKGROUND_ALIGNMENT_SEQ] == before

    def test_swapping_the_image_carries_the_stamp_along(self, gm):
        """The alignment is unchanged, so its stamp is too -- but it has to be
        on the payload or the client cannot judge what it is being sent."""
        gm_client, room, key = gm
        session = self.battlemap(gm_client, room, key)
        self.align(gm_client, room, key, 12.4)
        before = self.seq(session)
        gm_client.get_received()
        set_background(gm_client, room, "https://example.invalid/other.png")
        assert self.seq(session) == before

    @pytest.mark.parametrize("event_name,payload", [
        ("map_generate", {"mapWidth": 4, "mapHeight": 3, "discovered": False}),
        ("map_upload", {"mapText": "F\tF\n", "discovered": False}),
        ("clear_map", {"clearLocations": True}),
    ])
    def test_a_map_with_no_alignment_carries_no_stamp(self, gm, event_name, payload):
        gm_client, room, key = gm
        session = self.battlemap(gm_client, room, key)
        self.align(gm_client, room, key, 12.4)
        payload = dict(payload, room=room, gmKey=key)
        gm_client.emit(event_name, payload)
        assert self.seq(session) is None
        assert not any(k in session.mapData for k in mudfinder.BACKGROUND_ALIGNMENT_KEYS)

    def test_a_rejected_change_does_not_raise_it(self, gm):
        """A value that fails validation never lands, so nothing downstream
        should think there is something newer to fetch."""
        gm_client, room, key = gm
        session = self.battlemap(gm_client, room, key)
        before = self.seq(session)
        self.align(gm_client, room, key, "not a number")
        assert self.seq(session) == before

    def test_wrong_key_does_not_raise_it(self, gm):
        gm_client, room, key = gm
        session = self.battlemap(gm_client, room, key)
        before = self.seq(session)
        gm_client.emit("set_background_alignment", {
            "room": room, "gmKey": "wrong", "backgroundTilesWide": 12.4,
            "backgroundOffsetX": 0.0, "backgroundOffsetY": 0.0,
        })
        assert self.seq(session) == before

    def test_the_stamp_survives_a_save_and_load(self, gm):
        gm_client, room, key = gm
        session = self.battlemap(gm_client, room, key)
        self.align(gm_client, room, key, 12.4)
        restored = Session("other-room", "other-key", "restored")
        restored.from_json(session.gen_save())
        assert self.seq(restored) == self.seq(session)


class TestRollingAnAttack:
    """One press of the button is a full attack.

    The GM was typing /roll 1d20+6 and /roll 1d6+4 by hand, fourteen times a
    round for seven apes.
    """

    def roll(self, gm_client, room, key, **attack):
        payload = {"room": room, "gmKey": key, "charName": "Dire Ape",
                   "name": "bite", "attack": "+6", "damage": "1d6+4", "crit": ""}
        payload.update(attack)
        gm_client.emit("roll_attack", payload)
        return gm_client.get_received()

    def chat(self, received):
        return [p["args"][0]["chat"] for p in received if p["name"] == "chat"]

    def test_a_roll_is_reported(self, gm):
        gm_client, room, key = gm
        assert "Dire Ape" in self.chat(self.roll(gm_client, room, key))[0]

    def test_it_shows_the_die_the_bonus_and_the_total(self, gm):
        gm_client, room, key = gm
        line = self.chat(self.roll(gm_client, room, key))[0]
        assert re.search(r"d20\((\d+)\)\+6 = (\d+)", line)

    def test_the_total_is_the_die_plus_the_bonus(self, gm):
        gm_client, room, key = gm
        for _ in range(20):
            line = self.chat(self.roll(gm_client, room, key))[0]
            die, total = re.search(r"d20\((\d+)\)\+6 = (\d+)", line).groups()
            assert int(total) == int(die) + 6

    def test_the_damage_is_rolled_too(self, gm):
        gm_client, room, key = gm
        assert "damage" in self.chat(self.roll(gm_client, room, key))[0]

    def test_the_damage_is_within_range(self, gm):
        """1d6+4 is five to ten, and nothing else."""
        gm_client, room, key = gm
        for _ in range(20):
            damage = int(re.search(r"damage (\d+)",
                                   self.chat(self.roll(gm_client, room, key))[0]).group(1))
            assert 5 <= damage <= 10

    def test_only_the_leading_dice_are_rolled(self, gm):
        """The rest of the field is the crit and the riders. Handed the whole
        string, the dice roller reads "1d4/19-20" as a division and a short
        sword deals -19.9 damage."""
        gm_client, room, key = gm
        for _ in range(20):
            line = self.chat(self.roll(gm_client, room, key,
                                       name="short sword", attack="+2", damage="1d4/19-20"))[0]
            assert 1 <= int(re.search(r"damage (\d+)", line).group(1)) <= 4

    def test_a_rider_is_not_rolled_as_extra_dice(self, gm):
        """"1d6+4 plus 1d6 fire" is five to ten, not a hundred and thirty."""
        gm_client, room, key = gm
        for _ in range(20):
            line = self.chat(self.roll(gm_client, room, key, damage="1d6+4 plus 1d6 fire"))[0]
            assert 5 <= int(re.search(r"damage (\d+)", line).group(1)) <= 10

    def test_a_count_rolls_that_many_times(self, gm):
        gm_client, room, key = gm
        line = self.chat(self.roll(gm_client, room, key, name="2 claws"))[0]
        assert line.count("d20(") == 2

    def test_iteratives_roll_that_many_times(self, gm):
        gm_client, room, key = gm
        line = self.chat(self.roll(gm_client, room, key, attack="+18/+13/+8"))[0]
        assert line.count("d20(") == 3

    def test_a_count_and_iteratives_multiply(self, gm):
        gm_client, room, key = gm
        line = self.chat(self.roll(gm_client, room, key, name="2 claws", attack="+18/+13"))[0]
        assert line.count("d20(") == 4

    def test_a_threat_is_flagged(self, gm):
        """A nineteen on a 19-20 weapon is a threat; the same nineteen on a
        plain one is not."""
        gm_client, room, key = gm
        threats = plain = 0
        for _ in range(120):
            if "threat" in self.chat(self.roll(gm_client, room, key, crit="19-20"))[0]:
                threats += 1
            if "threat" in self.chat(self.roll(gm_client, room, key, crit=""))[0]:
                plain += 1
        assert threats > plain

    def test_a_weapon_with_no_crit_range_threatens_only_on_twenty(self, gm):
        gm_client, room, key = gm
        for _ in range(60):
            line = self.chat(self.roll(gm_client, room, key))[0]
            die = int(re.search(r"d20\((\d+)\)", line).group(1))
            assert ("threat" in line) == (die == 20)

    def test_an_attack_with_nothing_to_roll_says_only_the_attack(self, gm):
        gm_client, room, key = gm
        line = self.chat(self.roll(gm_client, room, key,
                                   name="telekinesis", damage="see below"))[0]
        assert "damage" not in line

    @pytest.mark.parametrize("bad", ["", None, "abc", "see below", "no physical attack"])
    def test_a_damage_field_that_is_not_dice_does_not_raise(self, gm, bad):
        gm_client, room, key = gm
        assert self.chat(self.roll(gm_client, room, key, damage=bad))

    @pytest.mark.parametrize("bad", ["", None, "abc"])
    def test_a_bonus_that_is_not_a_number_counts_as_zero(self, gm, bad):
        gm_client, room, key = gm
        line = self.chat(self.roll(gm_client, room, key, attack=bad))[0]
        die, bonus, total = re.search(r"d20\((\d+)\)([+-]\d+) = (\d+)", line).groups()
        assert int(bonus) == 0
        assert int(total) == int(die)

    def test_wrong_key_rolls_nothing_for_a_monster(self, gm):
        gm_client, room, _ = gm
        assert self.chat(self.roll(gm_client, room, "wrong")) == []

    def test_unknown_room_is_ignored(self, client):
        client.emit("roll_attack", {"room": "no-such-room", "gmKey": GM_KEY,
                                    "name": "bite", "attack": "+6", "damage": "1d6+4"})
        assert client.get_received() == []


class TestWhoSeesAnAttackRoll:
    """A monster's attack is the GM's business; a player's own weapon is not.

    Which follows the convention already in place rather than inventing one:
    the initiative rolls for a group of monsters already go to the GM alone,
    and /roll has always gone to everybody.
    """

    def test_a_monsters_roll_reaches_the_gm(self, browser_style_game):
        gm_client, room, key = browser_style_game
        gm_client.emit("roll_attack", {"room": room, "gmKey": key, "charName": "Dire Ape",
                                       "name": "bite", "attack": "+6", "damage": "1d6+4"})
        assert "chat" in event_names(gm_client.get_received())

    def test_a_monsters_roll_does_not_reach_the_players(self, browser_style_game):
        gm_client, room, key = browser_style_game
        player = mudfinder.socketio.test_client(mudfinder.app)
        player.emit("player_join", {"room": room, "charName": "Aria"})
        player.get_received()
        gm_client.emit("roll_attack", {"room": room, "gmKey": key, "charName": "Dire Ape",
                                       "name": "bite", "attack": "+6", "damage": "1d6+4"})
        assert "chat" not in event_names(player.get_received())

    def test_a_second_gm_view_sees_it(self, browser_style_game):
        gm_client, room, key = browser_style_game
        second = join_gm_socket(room, key)
        second.emit("roll_attack", {"room": room, "gmKey": key, "charName": "Dire Ape",
                                    "name": "bite", "attack": "+6", "damage": "1d6+4"})
        assert "chat" in event_names(gm_client.get_received())

    def test_a_player_rolling_their_own_weapon_is_public(self, browser_style_game):
        gm_client, room, _ = browser_style_game
        player = mudfinder.socketio.test_client(mudfinder.app)
        player.emit("player_join", {"room": room, "charName": "Aria"})
        player.get_received()
        player.emit("roll_attack", {"room": room, "charName": "Aria",
                                    "name": "longsword", "attack": "+7", "damage": "1d8+3"})
        assert "chat" in event_names(player.get_received())

    def test_a_player_cannot_roll_for_something_they_do_not_control(self, browser_style_game):
        """Otherwise a player could roll the monsters' attacks."""
        gm_client, room, key = browser_style_game
        gm_client.emit("add_units", {
            "room": room, "gmKey": key, "count": 1, "addToInitiative": False,
            "initiativeBonus": 0, "unit": {"charName": "Dire Ape", "controlledBy": "gm"}})
        gm_client.get_received()
        player = mudfinder.socketio.test_client(mudfinder.app)
        player.emit("player_join", {"room": room, "charName": "Aria"})
        player.get_received()
        player.emit("roll_attack", {"room": room, "charName": "Dire Ape",
                                    "name": "bite", "attack": "+6", "damage": "1d6+4"})
        assert "chat" not in event_names(player.get_received())


class TestSavingEditedAttacks:
    def test_the_gm_can_correct_a_bonus(self, gm):
        """The panel's boxes are editable, and a statblock is sometimes wrong."""
        gm_client, room, key = gm
        gm_client.emit("add_units", {
            "room": room, "gmKey": key, "count": 1, "addToInitiative": False,
            "initiativeBonus": 0,
            "unit": {"charName": "Dire Ape", "weapons": [["bite", "+6", "1d6+4", "", "", "", ""]]}})
        gm_client.get_received()
        gm_client.emit("update_unit", {
            "room": room, "gmKey": key, "unitNum": 0,
            "weapons": [["bite", "+9", "1d6+4", "", "", "", ""]]})
        assert mudfinder.ROOMS[room].unitList[0].weapons[0][1] == "+9"

    def test_an_update_that_omits_them_leaves_them_alone(self, gm):
        gm_client, room, key = gm
        gm_client.emit("add_units", {
            "room": room, "gmKey": key, "count": 1, "addToInitiative": False,
            "initiativeBonus": 0,
            "unit": {"charName": "Dire Ape", "weapons": [["bite", "+6", "1d6+4", "", "", "", ""]]}})
        gm_client.get_received()
        gm_client.emit("update_unit", {"room": room, "gmKey": key, "unitNum": 0, "color": "red"})
        assert mudfinder.ROOMS[room].unitList[0].weapons[0][1] == "+6"


class TestCastingASpell:
    """Spending one of a unit's castings.

    Counted on the server rather than in the browser, so the number survives a
    reload and two GM views cannot disagree about it.
    """

    def aboleth(self, gm_client, room, key):
        db = sqlite3.connect("mudfinder.sql")
        db.row_factory = sqlite3.Row
        creature = dict(db.execute(
            "select rowid as id, * from creatures where Name = 'Aboleth' limit 1").fetchone())
        gm_client.emit("add_units", {
            "room": room, "gmKey": key, "count": 1, "addToInitiative": False,
            "initiativeBonus": 0, "unit": mudfinder.creature_to_unit(creature)})
        gm_client.get_received()
        return mudfinder.ROOMS[room].unitList[0]

    def cast(self, gm_client, room, key, casting=0, unit_num=0, **overrides):
        payload = {"room": room, "gmKey": key, "unitNum": unit_num, "casting": casting}
        payload.update(overrides)
        gm_client.emit("cast_spell", payload)
        return gm_client.get_received()

    def test_casting_spends_one(self, gm):
        gm_client, room, key = gm
        unit = self.aboleth(gm_client, room, key)
        self.cast(gm_client, room, key)
        assert unit.castings[0]["uses"] == 2

    def test_the_daily_number_is_untouched(self, gm):
        gm_client, room, key = gm
        unit = self.aboleth(gm_client, room, key)
        self.cast(gm_client, room, key)
        assert unit.castings[0]["daily"] == 3

    def test_casting_says_what_was_cast(self, gm):
        gm_client, room, key = gm
        self.aboleth(gm_client, room, key)
        chat = event(self.cast(gm_client, room, key), "chat")["args"][0]["chat"]
        assert "dominate monster" in chat
        assert "2 left" in chat

    def test_a_pool_is_not_reported_as_casting_everything_in_it(self, gm):
        """Naming all five spells of a 3/day pool reads as though every one of
        them was cast."""
        gm_client, room, key = gm
        gm_client.emit("add_units", {
            "room": room, "gmKey": key, "count": 1, "addToInitiative": False,
            "initiativeBonus": 0, "unit": {"charName": "Planetar", "castings": [
                {"label": "3/day", "spells": "blade barrier, flame strike, raise dead",
                 "uses": 3, "daily": 3}]}})
        gm_client.get_received()
        chat = event(self.cast(gm_client, room, key), "chat")["args"][0]["chat"]
        assert "used a 3/day casting" in chat
        assert "blade barrier" not in chat

    def test_spending_the_last_one_leaves_none(self, gm):
        gm_client, room, key = gm
        unit = self.aboleth(gm_client, room, key)
        for _ in range(3):
            self.cast(gm_client, room, key)
        assert unit.castings[0]["uses"] == 0

    def test_it_cannot_go_below_zero(self, gm):
        """A second GM tab can be holding a stale count and offering a button
        for a casting that has already gone."""
        gm_client, room, key = gm
        unit = self.aboleth(gm_client, room, key)
        for _ in range(6):
            self.cast(gm_client, room, key)
        assert unit.castings[0]["uses"] == 0

    def test_a_spent_casting_says_nothing(self, gm):
        gm_client, room, key = gm
        self.aboleth(gm_client, room, key)
        for _ in range(3):
            self.cast(gm_client, room, key)
        assert "chat" not in event_names(self.cast(gm_client, room, key))

    def test_resetting_restores_everything(self, gm):
        gm_client, room, key = gm
        unit = self.aboleth(gm_client, room, key)
        self.cast(gm_client, room, key)
        gm_client.emit("reset_castings", {"room": room, "gmKey": key, "unitNum": 0})
        assert unit.castings[0]["uses"] == 3

    def test_wrong_key_casts_nothing(self, gm):
        gm_client, room, key = gm
        unit = self.aboleth(gm_client, room, key)
        self.cast(gm_client, room, "wrong")
        assert unit.castings[0]["uses"] == 3

    def test_wrong_key_resets_nothing(self, gm):
        gm_client, room, key = gm
        unit = self.aboleth(gm_client, room, key)
        self.cast(gm_client, room, key)
        gm_client.emit("reset_castings", {"room": room, "gmKey": "wrong", "unitNum": 0})
        assert unit.castings[0]["uses"] == 2

    @pytest.mark.parametrize("bad", ["abc", None, -1, 99, ""])
    def test_a_casting_that_is_not_there_does_not_raise(self, gm, bad):
        gm_client, room, key = gm
        unit = self.aboleth(gm_client, room, key)
        self.cast(gm_client, room, key, casting=bad)
        assert unit.castings[0]["uses"] == 3

    @pytest.mark.parametrize("bad", ["abc", None, -1, 99])
    def test_a_unit_that_is_not_there_does_not_raise(self, gm, bad):
        gm_client, room, key = gm
        unit = self.aboleth(gm_client, room, key)
        self.cast(gm_client, room, key, unit_num=bad)
        assert unit.castings[0]["uses"] == 3

    def test_unknown_room_is_ignored(self, client):
        client.emit("cast_spell", {"room": "no-such-room", "gmKey": GM_KEY,
                                   "unitNum": 0, "casting": 0})
        assert client.get_received() == []

    def test_the_count_is_on_the_unit_not_the_browser(self, gm):
        """Which is what makes it survive a reload."""
        gm_client, room, key = gm
        unit = self.aboleth(gm_client, room, key)
        self.cast(gm_client, room, key)
        assert Unit(unit.to_json()).castings[0]["uses"] == 2


class TestWhoSeesACast:
    def test_the_gm_is_told(self, browser_style_game):
        gm_client, room, key = browser_style_game
        gm_client.emit("add_units", {
            "room": room, "gmKey": key, "count": 1, "addToInitiative": False,
            "initiativeBonus": 0, "unit": {"charName": "Aboleth", "castings": [
                {"label": "3/day", "spells": "dominate monster", "uses": 3, "daily": 3}]}})
        gm_client.get_received()
        gm_client.emit("cast_spell", {"room": room, "gmKey": key, "unitNum": 0, "casting": 0})
        assert "chat" in event_names(gm_client.get_received())

    def test_the_players_are_not(self, browser_style_game):
        gm_client, room, key = browser_style_game
        gm_client.emit("add_units", {
            "room": room, "gmKey": key, "count": 1, "addToInitiative": False,
            "initiativeBonus": 0, "unit": {"charName": "Aboleth", "castings": [
                {"label": "3/day", "spells": "dominate monster", "uses": 3, "daily": 3}]}})
        gm_client.get_received()
        player = mudfinder.socketio.test_client(mudfinder.app)
        player.emit("player_join", {"room": room, "charName": "Aria"})
        player.get_received()
        gm_client.emit("cast_spell", {"room": room, "gmKey": key, "unitNum": 0, "casting": 0})
        assert "chat" not in event_names(player.get_received())


class TestRollingASave:
    def test_a_save_is_rolled_and_reported(self, browser_style_game):
        gm_client, room, key = browser_style_game
        gm_client.emit("roll_save", {"room": room, "gmKey": key,
                                     "charName": "Dire Ape", "save": "Ref", "bonus": 9})
        chats = [m for m in gm_client.get_received() if m["name"] == "chat"]
        assert chats
        line = chats[-1]["args"][0]["chat"]
        assert "Dire Ape" in line
        assert "Ref save" in line
        assert "d20(" in line

    def test_the_total_is_the_die_plus_the_bonus(self, browser_style_game):
        gm_client, room, key = browser_style_game
        gm_client.emit("roll_save", {"room": room, "gmKey": key,
                                     "charName": "Dire Ape", "save": "Will", "bonus": 4})
        line = [m for m in gm_client.get_received()
                if m["name"] == "chat"][-1]["args"][0]["chat"]
        die = int(re.search(r"d20\((\d+)\)", line).group(1))
        total = int(re.search(r"=\s*(-?\d+)$", line).group(1))
        assert total == die + 4

    def test_a_blank_bonus_rolls_flat(self, browser_style_game):
        gm_client, room, key = browser_style_game
        gm_client.emit("roll_save", {"room": room, "gmKey": key,
                                     "charName": "Dire Ape", "save": "Fort", "bonus": ""})
        line = [m for m in gm_client.get_received()
                if m["name"] == "chat"][-1]["args"][0]["chat"]
        die = int(re.search(r"d20\((\d+)\)", line).group(1))
        assert int(re.search(r"=\s*(-?\d+)$", line).group(1)) == die

    def test_only_the_three_saves_are_rolled(self, browser_style_game):
        """The name goes into everyone's chat, so it is one of ours or it is
        nothing -- not whatever the client felt like sending."""
        gm_client, room, key = browser_style_game
        gm_client.emit("roll_save", {"room": room, "gmKey": key, "charName": "Dire Ape",
                                     "save": "<script>alert(1)</script>", "bonus": 2})
        assert "chat" not in event_names(gm_client.get_received())

    def test_an_unknown_room_is_ignored(self, client):
        client.emit("roll_save", {"room": "no-such-room", "gmKey": GM_KEY,
                                  "charName": "Nobody", "save": "Will", "bonus": 1})
        assert client.get_received() == []


class TestWhoSeesASaveRoll:
    """The same rule an attack roll goes by, and it matters more here: the
    party learning that the lich made its save is the game, learning that it
    made it by eleven is not."""

    def test_a_monsters_save_does_not_reach_the_players(self, browser_style_game):
        gm_client, room, key = browser_style_game
        player = mudfinder.socketio.test_client(mudfinder.app)
        player.emit("player_join", {"room": room, "charName": "Aria"})
        player.get_received()
        gm_client.emit("roll_save", {"room": room, "gmKey": key,
                                     "charName": "Dire Ape", "save": "Fort", "bonus": 7})
        assert "chat" not in event_names(player.get_received())

    def test_a_player_rolling_their_own_save_is_public(self, browser_style_game):
        gm_client, room, _ = browser_style_game
        player = mudfinder.socketio.test_client(mudfinder.app)
        player.emit("player_join", {"room": room, "charName": "Aria"})
        player.get_received()
        player.emit("roll_save", {"room": room, "charName": "Aria",
                                  "save": "Will", "bonus": 5})
        assert "chat" in event_names(player.get_received())

    def test_and_the_gm_sees_it_too(self, browser_style_game):
        gm_client, room, _ = browser_style_game
        player = mudfinder.socketio.test_client(mudfinder.app)
        player.emit("player_join", {"room": room, "charName": "Aria"})
        player.get_received()
        gm_client.get_received()
        player.emit("roll_save", {"room": room, "charName": "Aria",
                                  "save": "Will", "bonus": 5})
        assert "chat" in event_names(gm_client.get_received())

    def test_a_player_cannot_roll_a_monsters_save(self, browser_style_game):
        """Otherwise a player could roll the saves the GM is making against
        their own spells."""
        gm_client, room, key = browser_style_game
        gm_client.emit("add_units", {
            "room": room, "gmKey": key, "count": 1, "addToInitiative": False,
            "initiativeBonus": 0, "unit": {"charName": "Dire Ape", "controlledBy": "gm"}})
        gm_client.get_received()
        player = mudfinder.socketio.test_client(mudfinder.app)
        player.emit("player_join", {"room": room, "charName": "Aria"})
        player.get_received()
        player.emit("roll_save", {"room": room, "charName": "Dire Ape",
                                  "save": "Fort", "bonus": 7})
        assert "chat" not in event_names(player.get_received())


class TestLinkingTwoTilesAsAStaircase:
    """A map holds more than one level by drawing them as separate parts of the
    one grid; a staircase joins a tile in one to a tile in the other."""

    def mapped(self, room, width=8, height=4):
        mudfinder.ROOMS[room].mapData["mapArray"] = [
            [{"tile": "floorTile", "walkable": True, "seen": True,
              "secret": False, "x": x, "y": y}
             for x in range(width)] for y in range(height)]
        return mudfinder.ROOMS[room].mapData["mapArray"]

    def tile(self, room, y, x):
        return mudfinder.ROOMS[room].mapData["mapArray"][y][x]

    def link(self, client, room, key, a, b):
        client.emit("link_warp", {"room": room, "gmKey": key,
                                  "fromY": a[0], "fromX": a[1],
                                  "toY": b[0], "toX": b[1]})

    def test_both_ends_carry_the_link(self, browser_style_game):
        gm_client, room, key = browser_style_game
        self.mapped(room)
        self.link(gm_client, room, key, (1, 1), (2, 6))
        assert self.tile(room, 1, 1)["warp"] == [2, 6]
        assert self.tile(room, 2, 6)["warp"] == [1, 1]

    def test_the_same_tile_twice_takes_it_out(self, browser_style_game):
        gm_client, room, key = browser_style_game
        self.mapped(room)
        self.link(gm_client, room, key, (1, 1), (2, 6))
        self.link(gm_client, room, key, (1, 1), (1, 1))
        assert "warp" not in self.tile(room, 1, 1)
        assert "warp" not in self.tile(room, 2, 6)

    def test_relinking_lets_go_of_the_old_partner(self, browser_style_game):
        """Otherwise the tile left behind still points at a staircase that no
        longer points back, and is drawn as one."""
        gm_client, room, key = browser_style_game
        self.mapped(room)
        self.link(gm_client, room, key, (1, 1), (2, 6))
        self.link(gm_client, room, key, (1, 1), (3, 4))
        assert self.tile(room, 1, 1)["warp"] == [3, 4]
        assert self.tile(room, 3, 4)["warp"] == [1, 1]
        assert "warp" not in self.tile(room, 2, 6)

    def test_painting_over_a_staircase_takes_the_link_with_it(self, browser_style_game):
        gm_client, room, key = browser_style_game
        self.mapped(room)
        self.link(gm_client, room, key, (1, 1), (2, 6))
        gm_client.emit("map_edit", {
            "room": room, "gmKey": key, "relative_x": 8, "relative_y": 8,
            "tiles": [{"newTile": "wallTile", "xCoord": 1, "yCoord": 1}]})
        assert "warp" not in self.tile(room, 1, 1)
        assert "warp" not in self.tile(room, 2, 6)

    def test_the_gm_key_is_checked(self, browser_style_game):
        gm_client, room, _ = browser_style_game
        self.mapped(room)
        self.link(gm_client, room, "not-the-key", (1, 1), (2, 6))
        assert "warp" not in self.tile(room, 1, 1)

    def test_a_coordinate_off_the_map_is_ignored(self, browser_style_game):
        gm_client, room, key = browser_style_game
        self.mapped(room)
        self.link(gm_client, room, key, (1, 1), (99, 99))
        assert "warp" not in self.tile(room, 1, 1)

    def test_rubbish_coordinates_do_not_raise(self, browser_style_game):
        gm_client, room, key = browser_style_game
        self.mapped(room)
        gm_client.emit("link_warp", {"room": room, "gmKey": key,
                                     "fromY": "up", "fromX": None,
                                     "toY": 2, "toX": 6})
        assert "warp" not in self.tile(room, 2, 6)

    def test_an_unknown_room_is_ignored(self, client):
        client.emit("link_warp", {"room": "no-such-room", "gmKey": GM_KEY,
                                  "fromY": 1, "fromX": 1, "toY": 2, "toX": 2})
        assert client.get_received() == []

    def test_the_change_reaches_the_gm(self, browser_style_game):
        gm_client, room, key = browser_style_game
        self.mapped(room)
        gm_client.get_received()
        self.link(gm_client, room, key, (1, 1), (2, 6))
        assert "gm_map_update" in event_names(gm_client.get_received())

    def test_a_player_is_not_told_about_one_in_the_dark(self, browser_style_game):
        """The far end is somewhere they have never been, so the mark on it
        would show a way through where the fog says there is nothing."""
        gm_client, room, key = browser_style_game
        grid = self.mapped(room)
        grid[2][6]["seen"] = False
        player = mudfinder.socketio.test_client(mudfinder.app)
        player.emit("player_join", {"room": room, "charName": "Aria"})
        player.get_received()
        self.link(gm_client, room, key, (1, 1), (2, 6))
        updates = [m for m in player.get_received() if m["name"] == "player_map_update"]
        assert updates
        sent = {(t["y"], t["x"]): t for t in updates[-1]["args"][0]["mapArray"]}
        assert "warp" not in sent[(2, 6)]
        assert sent[(1, 1)]["warp"] == [2, 6]


class TestSettingAnImageTellsTheGm:
    """The GM sets a unit's token from their own sheet, so the GM is the one
    person who has to be told about it.

    do_update is the players' event: the GM view has no handler for it and is
    not in the room it goes to either, so the GM who had just chosen a token
    watched nothing happen until something unrelated refreshed their page.
    """

    def add_unit(self, gm_client, room, key):
        gm_client.emit("add_units", {
            "room": room, "gmKey": key, "count": 1, "addToInitiative": False,
            "initiativeBonus": 0, "unit": {"charName": "Scout", "controlledBy": "gm"}})
        gm_client.get_received()

    def test_a_unit_token_reaches_the_gm(self, browser_style_game):
        gm_client, room, key = browser_style_game
        self.add_unit(gm_client, room, key)
        gm_client.emit("image_upload", room, "/static/images/profile.svg",
                       "unitToken", "0")
        assert "gm_update" in event_names(gm_client.get_received())

    def test_and_the_token_is_in_what_it_sends(self, browser_style_game):
        gm_client, room, key = browser_style_game
        self.add_unit(gm_client, room, key)
        gm_client.emit("image_upload", room, "/static/images/profile.svg",
                       "unitToken", "0")
        update = [m for m in gm_client.get_received()
                  if m["name"] == "gm_update"][-1]["args"][0]
        assert update["unitList"][0]["token"] == "/static/images/profile.svg"

    def test_the_players_are_still_told(self, browser_style_game):
        """The token is on the board, so it was never only the GM's business."""
        gm_client, room, key = browser_style_game
        self.add_unit(gm_client, room, key)
        player = mudfinder.socketio.test_client(mudfinder.app)
        player.emit("player_join", {"room": room, "charName": "Aria"})
        player.get_received()
        gm_client.emit("image_upload", room, "/static/images/profile.svg",
                       "unitToken", "0")
        assert "do_update" in event_names(player.get_received())

    def test_a_players_own_token_reaches_the_gm_too(self, browser_style_game):
        """Same emit, so the character images had the same hole in them."""
        gm_client, room, key = browser_style_game
        player = mudfinder.socketio.test_client(mudfinder.app)
        player.emit("player_join", {"room": room, "charName": "Aria"})
        player.get_received()
        gm_client.get_received()
        player.emit("image_upload", room, "/static/images/profile.svg",
                    "charToken", "Aria")
        assert "gm_update" in event_names(gm_client.get_received())


class TestLoreReachesTheGmToo:
    """A GM joins gmRoom and never the room itself, so a broadcast to the room
    is everybody except the one person most likely to have just changed
    something. Adding a page of lore left the GM's own tab showing what was
    there before it, until they reloaded."""

    def test_adding_lore_reaches_the_gm(self, browser_style_game):
        gm_client, room, _ = browser_style_game
        gm_client.get_received()
        gm_client.emit("lore_url", room, "", "The Broken Seal", "A cracked disc.", "gm")
        assert "showLore" in event_names(gm_client.get_received())

    def test_and_carries_the_new_page(self, browser_style_game):
        gm_client, room, _ = browser_style_game
        gm_client.emit("lore_url", room, "", "The Broken Seal", "A cracked disc.", "gm")
        sent = [m for m in gm_client.get_received()
                if m["name"] == "showLore"][-1]["args"][0]
        assert [page["loreName"] for page in sent["lore"]] == ["The Broken Seal"]

    def test_sharing_it_reaches_the_gm(self, browser_style_game):
        gm_client, room, key = browser_style_game
        gm_client.emit("lore_url", room, "", "The Broken Seal", "A cracked disc.", "gm")
        gm_client.get_received()
        gm_client.emit("lore_visible", room, key, 0)
        assert "showLore" in event_names(gm_client.get_received())

    def test_the_players_are_still_told(self, browser_style_game):
        gm_client, room, _ = browser_style_game
        player = mudfinder.socketio.test_client(mudfinder.app)
        player.emit("player_join", {"room": room, "charName": "Aria"})
        player.get_received()
        gm_client.emit("lore_url", room, "", "The Broken Seal", "A cracked disc.", "gm")
        assert "showLore" in event_names(player.get_received())

    def test_and_so_are_the_spectators(self, browser_style_game):
        gm_client, room, _ = browser_style_game
        spectator = mudfinder.socketio.test_client(mudfinder.app)
        spectator.emit("spectator_join", {"room": room})
        spectator.get_received()
        gm_client.emit("lore_url", room, "", "The Broken Seal", "A cracked disc.", "gm")
        assert "showLore" in event_names(spectator.get_received())


class TestTurningAToken:
    """Purely how it looks: Pathfinder has no facing, so nothing reads the
    angle but the renderer. A player may turn what they control; the GM may
    turn anything."""

    def add_unit(self, gm_client, room, key, name="Goblin", controlled="gm"):
        gm_client.emit("add_units", {
            "room": room, "gmKey": key, "count": 1, "addToInitiative": False,
            "initiativeBonus": 0,
            "unit": {"charName": name, "controlledBy": controlled}})
        gm_client.get_received()

    def rotation(self, room, index=0):
        return mudfinder.ROOMS[room].unitList[index].rotation

    def test_a_token_starts_square(self, browser_style_game):
        gm_client, room, key = browser_style_game
        self.add_unit(gm_client, room, key)
        assert self.rotation(room) == 0

    def test_the_gm_turns_it_a_quarter(self, browser_style_game):
        gm_client, room, key = browser_style_game
        self.add_unit(gm_client, room, key)
        gm_client.emit("rotate_unit", {"room": room, "gmKey": key,
                                       "unitNum": 0, "clockwise": True})
        assert self.rotation(room) == 90

    def test_and_the_other_way(self, browser_style_game):
        gm_client, room, key = browser_style_game
        self.add_unit(gm_client, room, key)
        gm_client.emit("rotate_unit", {"room": room, "gmKey": key,
                                       "unitNum": 0, "clockwise": False})
        assert self.rotation(room) == 270

    def test_it_comes_back_round(self, browser_style_game):
        """Kept in 0-359, so a save reads as a facing rather than as a tally of
        every time anybody turned it."""
        gm_client, room, key = browser_style_game
        self.add_unit(gm_client, room, key)
        for _ in range(4):
            gm_client.emit("rotate_unit", {"room": room, "gmKey": key,
                                           "unitNum": 0, "clockwise": True})
        assert self.rotation(room) == 0

    def test_the_change_reaches_everyone(self, browser_style_game):
        """It is on the board, so it is not the turner's business alone."""
        gm_client, room, key = browser_style_game
        self.add_unit(gm_client, room, key)
        player = mudfinder.socketio.test_client(mudfinder.app)
        player.emit("player_join", {"room": room, "charName": "Aria"})
        player.get_received()
        gm_client.get_received()
        gm_client.emit("rotate_unit", {"room": room, "gmKey": key,
                                       "unitNum": 0, "clockwise": True})
        assert "gm_update" in event_names(gm_client.get_received())
        assert "do_update" in event_names(player.get_received())

    def test_a_player_turns_what_they_control(self, browser_style_game):
        gm_client, room, key = browser_style_game
        player = mudfinder.socketio.test_client(mudfinder.app)
        player.emit("player_join", {"room": room, "charName": "Aria"})
        player.get_received()
        theirs = next(i for i, u in enumerate(mudfinder.ROOMS[room].unitList)
                      if u.controlledBy == "Aria")
        player.emit("rotate_unit", {"room": room, "unitNum": theirs,
                                    "requestingPlayer": "Aria", "clockwise": True})
        assert self.rotation(room, theirs) == 90

    def test_but_not_somebody_elses(self, browser_style_game):
        """Otherwise a player could spin the monsters, or another character."""
        gm_client, room, key = browser_style_game
        self.add_unit(gm_client, room, key)
        player = mudfinder.socketio.test_client(mudfinder.app)
        player.emit("player_join", {"room": room, "charName": "Aria"})
        player.get_received()
        player.emit("rotate_unit", {"room": room, "unitNum": 0,
                                    "requestingPlayer": "Aria", "clockwise": True})
        assert self.rotation(room) == 0

    def test_nor_by_claiming_to_be_someone_else(self, browser_style_game):
        """The name is checked against what the unit says controls it, not
        against what the sender says they are called."""
        gm_client, room, key = browser_style_game
        self.add_unit(gm_client, room, key, controlled="Aria")
        stranger = mudfinder.socketio.test_client(mudfinder.app)
        stranger.emit("player_join", {"room": room, "charName": "Mal"})
        stranger.get_received()
        stranger.emit("rotate_unit", {"room": room, "unitNum": 0,
                                      "requestingPlayer": "Mal", "clockwise": True})
        assert self.rotation(room) == 0

    def test_a_wrong_gm_key_turns_nothing(self, browser_style_game):
        gm_client, room, _ = browser_style_game
        self.add_unit(gm_client, room, GM_KEY)
        gm_client.emit("rotate_unit", {"room": room, "gmKey": "not-the-key",
                                       "unitNum": 0, "clockwise": True})
        assert self.rotation(room) == 0

    def test_a_unit_that_is_not_there_is_ignored(self, browser_style_game):
        gm_client, room, key = browser_style_game
        self.add_unit(gm_client, room, key)
        gm_client.emit("rotate_unit", {"room": room, "gmKey": key,
                                       "unitNum": 99, "clockwise": True})
        assert self.rotation(room) == 0

    def test_an_unknown_room_is_ignored(self, client):
        client.emit("rotate_unit", {"room": "no-such-room", "gmKey": GM_KEY,
                                    "unitNum": 0, "clockwise": True})
        assert client.get_received() == []

    def test_an_angle_saved_as_rubbish_is_treated_as_square(self, browser_style_game):
        """A save from before tokens could turn, or one edited by hand."""
        gm_client, room, key = browser_style_game
        self.add_unit(gm_client, room, key)
        mudfinder.ROOMS[room].unitList[0].rotation = "sideways"
        gm_client.emit("rotate_unit", {"room": room, "gmKey": key,
                                       "unitNum": 0, "clockwise": True})
        assert self.rotation(room) == 90
