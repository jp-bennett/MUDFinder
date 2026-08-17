"""Tests for the Unit / Player / Session data model.

These cover the save-file round trip, which is what protects existing games
from a bad refactor, plus the initiative ordering rules.
"""

import pytest

from helpers import make_player, make_unit
from player import Player
from session import Session, BACKGROUND_ALIGNMENT_KEYS
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


class TestBackgroundAlignmentPersistence:
    """Where an uploaded battlemap sits behind the grid.

    Stored in grid squares rather than pixels, so the numbers stay meaningful
    if the tile size ever changes.
    """

    @pytest.fixture
    def aligned(self):
        session = Session("room-1", "key-1", "Battlemap")
        session.mapData["mapArray"] = [[{"tile": "floorTile", "walkable": True,
                                         "seen": True, "secret": False, "x": 0, "y": 0}]]
        session.mapData["mapBackground"] = "get_image.html?room=room-1&id=abc"
        session.mapData["backgroundTilesWide"] = 24.5
        session.mapData["backgroundOffsetX"] = -1.25
        session.mapData["backgroundOffsetY"] = -0.8
        return session

    def test_alignment_survives_a_save_and_load(self, aligned):
        restored = Session("room-1", "key-1", "placeholder")
        restored.from_json(aligned.gen_save())
        assert restored.mapData["backgroundTilesWide"] == 24.5
        assert restored.mapData["backgroundOffsetX"] == -1.25
        assert restored.mapData["backgroundOffsetY"] == -0.8

    def test_the_background_survives_with_it(self, aligned):
        restored = Session("room-1", "key-1", "placeholder")
        restored.from_json(aligned.gen_save())
        assert restored.mapData["mapBackground"] == "get_image.html?room=room-1&id=abc"

    def test_a_save_from_before_the_feature_still_loads(self, aligned):
        blob = aligned.gen_save()
        for key in BACKGROUND_ALIGNMENT_KEYS:
            del blob["mapData"][key]
        restored = Session("room-1", "key-1", "placeholder")
        restored.from_json(blob)
        assert restored.mapData["mapArray"]

    def test_an_older_save_is_left_unaligned(self, aligned):
        """Deliberate: absent keys are what makes the client draw it the old
        way, so an existing game keeps looking exactly as it did."""
        blob = aligned.gen_save()
        for key in BACKGROUND_ALIGNMENT_KEYS:
            del blob["mapData"][key]
        restored = Session("room-1", "key-1", "placeholder")
        restored.from_json(blob)
        assert not any(key in restored.mapData for key in BACKGROUND_ALIGNMENT_KEYS)

    def test_players_are_given_the_alignment(self, aligned):
        """Or their artwork will not line up with the grid they move on."""
        player_view = aligned.player_map()
        assert player_view["backgroundTilesWide"] == 24.5
        assert player_view["backgroundOffsetX"] == -1.25
        assert player_view["backgroundOffsetY"] == -0.8

    def test_players_of_an_unaligned_map_are_given_nothing(self, aligned):
        for key in BACKGROUND_ALIGNMENT_KEYS:
            del aligned.mapData[key]
        assert not any(key in aligned.player_map() for key in BACKGROUND_ALIGNMENT_KEYS)


class TestLightLevelPersistence:
    """A painted light level is a key on the tile, and its absence is normal.

    Absence rather than an explicit "normal" is what makes every map saved
    before the feature existed a fully lit one, with no migration to run.
    """

    @pytest.fixture
    def lit(self):
        session = Session("room-1", "key-1", "Cavern")
        session.mapData["mapArray"] = [[
            {"tile": "floorTile", "walkable": True, "seen": True,
             "secret": False, "x": x, "y": 0}
            for x in range(3)]]
        session.mapData["mapArray"][0][0]["light"] = "darkness"
        session.mapData["mapArray"][0][1]["light"] = "bright"
        return session

    def test_light_survives_a_save_and_load(self, lit):
        restored = Session("room-1", "key-1", "placeholder")
        restored.from_json(lit.gen_save())
        row = restored.mapData["mapArray"][0]
        assert [tile.get("light") for tile in row] == ["darkness", "bright", None]

    def test_a_normally_lit_square_stores_nothing(self, lit):
        assert "light" not in lit.mapData["mapArray"][0][2]

    def test_a_save_written_before_the_feature_loads_lit(self, lit):
        """The compatibility hinge. Every tile in an older save arrives without
        the key, and every read has to cope with that rather than default it
        in -- an unlit map is exactly what those games were."""
        blob = lit.gen_save()
        for tile in blob["mapData"]["mapArray"][0]:
            tile.pop("light", None)
        restored = Session("room-1", "key-1", "placeholder")
        restored.from_json(blob)
        assert all("light" not in tile for tile in restored.mapData["mapArray"][0])

    def test_players_are_given_the_light_they_can_see(self, lit):
        row = lit.player_map()["mapArray"][0]
        assert [tile.get("light") for tile in row] == ["darkness", "bright", None]

    def test_players_are_given_none_of_the_light_they_cannot(self, lit):
        for tile in lit.mapData["mapArray"][0]:
            tile["seen"] = False
        assert all("light" not in tile for tile in lit.player_map()["mapArray"][0])


class TestVisionFields:
    """How a creature copes with the light on the map.

    The checkboxes for these have been on the GM's sheet, and on the wire, and
    assigned by the update handler -- but the fields were in neither Unit's
    constructor nor its to_json, so the value reached no client and survived no
    save. The GM's setting appeared to revert the moment the next update landed.
    """

    def test_a_creature_starts_with_neither(self, ):
        unit = make_unit()
        assert unit.darkvision is False
        assert unit.lowLight is False

    def test_they_can_be_set(self):
        unit = make_unit(darkvision=True, lowLight=True)
        assert unit.darkvision is True
        assert unit.lowLight is True

    def test_they_reach_the_clients(self):
        """to_json is what gm_update carries, so a field missing from it is a
        field the sheet can never show."""
        saved = make_unit(darkvision=True, lowLight=True).to_json()
        assert saved["darkvision"] is True
        assert saved["lowLight"] is True

    def test_they_survive_a_round_trip(self):
        unit = Unit(make_unit(darkvision=True, lowLight=True).to_json())
        assert unit.darkvision is True
        assert unit.lowLight is True

    def test_the_other_two_that_had_the_same_defect(self):
        saved = make_unit(trapfinding=True, permanentAbilities="Regeneration 5").to_json()
        assert saved["trapfinding"] is True
        assert saved["permanentAbilities"] == "Regeneration 5"

    def test_players_have_them_too(self):
        """Player subclasses Unit, so the party gets the same fields."""
        assert make_player(darkvision=True).darkvision is True

    def test_a_unit_saved_before_the_fields_existed_loads(self):
        saved = make_unit().to_json()
        for key in ["darkvision", "lowLight", "trapfinding", "permanentAbilities"]:
            del saved[key]
        unit = Unit(saved)
        assert unit.darkvision is False
        assert unit.permanentAbilities == ""
