"""Tests for the Unit / Player / Session data model.

These cover the save-file round trip, which is what protects existing games
from a bad refactor, plus the initiative ordering rules.
"""

import pytest

from conftest import make_player, make_unit
from player import Player
from session import Session
from unit import Unit, default


class TestDefault:
    def test_returns_value_when_present(self):
        assert default({"a": 1}, "a", 99) == 1

    def test_returns_default_when_absent(self):
        assert default({}, "a", 99) == 99

    def test_present_but_falsy_value_wins_over_default(self):
        assert default({"a": 0}, "a", 99) == 0


class TestUnit:
    def test_char_name_is_required(self):
        with pytest.raises(KeyError):
            Unit({})

    def test_defaults_are_applied(self):
        unit = make_unit()
        assert unit.alignment == "N"
        assert unit.size == "medium"
        assert unit.type == "mob"
        assert unit.location == [-1, -1]

    def test_supplied_values_override_defaults(self):
        unit = make_unit(size="large", alignment="CE", HP="27")
        assert unit.size == "large"
        assert unit.alignment == "CE"
        assert unit.HP == "27"

    def test_each_unit_gets_a_distinct_uuid(self):
        assert make_unit().uuid != make_unit().uuid

    def test_supplied_uuid_is_preserved(self):
        assert make_unit(uuid="fixed-uuid").uuid == "fixed-uuid"

    def test_location_defaults_from_x_and_y(self):
        unit = make_unit(x=3, y=4)
        assert unit.location == [3, 4]

    def test_placed_unit_occupies_its_tile(self):
        unit = make_unit(location=[2, 2])
        assert [2, 2] in unit.occupied_tiles

    def test_unplaced_unit_occupies_nothing(self):
        assert make_unit().occupied_tiles == []

    def test_to_json_round_trips_through_the_constructor(self):
        original = make_unit(HP="15", size="large", color="red", perception=7)
        restored = Unit(original.to_json())
        assert restored.to_json() == original.to_json()

    def test_to_json_is_serialisable(self):
        import json

        json.dumps(make_unit().to_json())


class TestPlayer:
    def test_player_type_defaults_to_player(self):
        assert make_player().type == "player"

    def test_player_reveals_map(self):
        assert make_player().revealsMap is True

    def test_player_is_controlled_by_itself(self):
        assert make_player().controlledBy == "Aria"

    def test_new_player_gets_an_empty_inventory(self):
        player = make_player()
        assert player.inventories["Aria"] == {"gp": [], "inventory": []}

    def test_supplied_inventories_are_kept(self):
        inventories = {"Aria": {"gp": [10], "inventory": ["rope"]}}
        assert make_player(inventories=inventories).inventories == inventories

    def test_starts_disconnected(self):
        player = make_player()
        assert player.connected is False
        assert player.connections == 0

    def test_to_json_includes_player_fields(self):
        blob = make_player(level="3", race="elf").to_json()
        assert blob["level"] == "3"
        assert blob["race"] == "elf"
        assert blob["type"] == "player"
        assert "inventories" in blob

    def test_to_json_round_trips_through_the_constructor(self):
        original = make_player(level="5", HP="30", deity="Sarenrae")
        restored = Player(original.to_json())
        assert restored.to_json() == original.to_json()


class TestInsertInitiative:
    def test_units_are_ordered_highest_first(self):
        session = Session("r", "k", "n")
        for name, roll in [("A", 10), ("B", 20), ("C", 15)]:
            session.insert_initiative(make_unit(charName=name, initiative=roll))
        assert [u.charName for u in session.initiativeList] == ["B", "C", "A"]

    def test_init_numbers_are_renumbered_on_insert(self):
        session = Session("r", "k", "n")
        for name, roll in [("A", 10), ("B", 20), ("C", 15)]:
            session.insert_initiative(make_unit(charName=name, initiative=roll))
        assert [u.initNum for u in session.initiativeList] == [0, 1, 2]

    def test_a_unit_without_initiative_is_not_added(self):
        session = Session("r", "k", "n")
        session.insert_initiative(make_unit())
        assert session.initiativeList == []

    def test_zero_initiative_is_not_added(self):
        # Falsy initiative is treated as "hasn't rolled yet".
        session = Session("r", "k", "n")
        session.insert_initiative(make_unit(initiative=0))
        assert session.initiativeList == []

    def test_ties_do_not_lose_a_combatant(self):
        session = Session("r", "k", "n")
        for name in ["A", "B", "C"]:
            session.insert_initiative(make_unit(charName=name, initiative=12))
        assert len(session.initiativeList) == 3


class TestOrderInitiativeList:
    def test_sorts_descending_and_renumbers(self):
        session = Session("r", "k", "n")
        session.initiativeList = [
            make_unit(charName="A", initiative=5),
            make_unit(charName="B", initiative=25),
            make_unit(charName="C", initiative=15),
        ]
        session.order_initiative_list()
        assert [u.charName for u in session.initiativeList] == ["B", "C", "A"]
        assert [u.initNum for u in session.initiativeList] == [0, 1, 2]

    def test_string_initiatives_sort_numerically(self):
        session = Session("r", "k", "n")
        session.initiativeList = [
            make_unit(charName="A", initiative="9"),
            make_unit(charName="B", initiative="10"),
        ]
        session.order_initiative_list()
        assert [u.charName for u in session.initiativeList] == ["B", "A"]


class TestNumberUnits:
    def test_unit_numbers_match_list_positions(self):
        session = Session("r", "k", "n")
        session.unitList = [make_unit(charName=n) for n in "ABC"]
        session.number_units()
        assert [u.unitNum for u in session.unitList] == [0, 1, 2]

    def test_renumbering_after_a_removal(self):
        session = Session("r", "k", "n")
        session.unitList = [make_unit(charName=n) for n in "ABC"]
        session.number_units()
        del session.unitList[1]
        session.number_units()
        assert [(u.charName, u.unitNum) for u in session.unitList] == [("A", 0), ("C", 1)]


class TestSessionSerialisation:
    @pytest.fixture
    def populated(self):
        session = Session("room-1", "key-1", "Saved Game")
        player = make_player(HP="12")
        session.unitList.append(player)
        session.playerList["Aria"] = player
        session.unitList.append(make_unit(charName="Goblin", initiative=14))
        session.number_units()
        session.insert_initiative(session.unitList[1])
        session.unitList[1].inInit = True
        session.mapData["mapArray"] = [[0, 0], [0, 0]]
        return session

    def test_gen_save_is_json_serialisable(self, populated):
        import json

        json.dumps(populated.gen_save())

    def test_gen_save_carries_the_gm_key(self, populated):
        assert populated.gen_save()["gmKey"] == "key-1"

    def test_round_trip_restores_units(self, populated):
        restored = Session("room-1", "key-1", "placeholder")
        restored.from_json(populated.gen_save())
        assert [u.charName for u in restored.unitList] == ["Aria", "Goblin"]

    def test_round_trip_restores_the_name(self, populated):
        restored = Session("room-1", "key-1", "placeholder")
        restored.from_json(populated.gen_save())
        assert restored.name == "Saved Game"

    def test_round_trip_rebuilds_players_as_player_objects(self, populated):
        restored = Session("room-1", "key-1", "placeholder")
        restored.from_json(populated.gen_save())
        assert isinstance(restored.playerList["Aria"], Player)
        assert restored.playerList["Aria"].HP == "12"

    def test_round_trip_preserves_player_identity_between_lists(self, populated):
        restored = Session("room-1", "key-1", "placeholder")
        restored.from_json(populated.gen_save())
        assert restored.playerList["Aria"] is restored.unitList[0]

    def test_round_trip_restores_the_initiative_list(self, populated):
        restored = Session("room-1", "key-1", "placeholder")
        restored.from_json(populated.gen_save())
        assert [u.charName for u in restored.initiativeList] == ["Goblin"]

    def test_round_trip_restores_the_map(self, populated):
        restored = Session("room-1", "key-1", "placeholder")
        restored.from_json(populated.gen_save())
        assert restored.mapData["mapArray"] == [[0, 0], [0, 0]]

    def test_round_trip_numbers_units(self, populated):
        restored = Session("room-1", "key-1", "placeholder")
        restored.from_json(populated.gen_save())
        assert [u.unitNum for u in restored.unitList] == [0, 1]

    def test_map_background_defaults_are_filled_in(self, populated):
        """A save written before the background feature still loads."""
        blob = populated.gen_save()
        blob["mapData"] = {"mapArray": [[0]]}
        restored = Session("room-1", "key-1", "placeholder")
        restored.from_json(blob)
        assert restored.mapData["showBackground"] is True
        assert restored.mapData["mapBackground"].endswith("mapbackground.jpg")

    def test_to_json_lists_saved_encounters_by_name_only(self, populated):
        populated.savedEncounters = {"Ambush": {"units": []}}
        assert populated.to_json()["savedEncounters"] == ["Ambush"]

    def test_gen_save_keeps_full_saved_encounters(self, populated):
        populated.savedEncounters = {"Ambush": {"units": []}}
        assert populated.gen_save()["savedEncounters"] == {"Ambush": {"units": []}}
