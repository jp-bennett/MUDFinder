"""Tests for the Socket.IO event handlers.

This is the layer that broke silently when the server-side Socket.IO libraries
drifted ahead of the vendored 2.x browser client, so it is worth keeping
covered: if a dependency bump breaks the wire protocol or the handler
signatures, these fail rather than the app merely failing to work in a browser.
"""

import pytest

import mudfinder
from conftest import GM_KEY, event, event_names


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
