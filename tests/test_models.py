"""Tests for the Unit / Player / Session data model.

These cover the save-file round trip, which is what protects existing games
from a bad refactor, plus the initiative ordering rules.
"""

import os
import re
import sqlite3
import urllib.parse

import pytest

import mudfinder
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


class TestCreatureToUnit:
    """Turning a bestiary row into a unit.

    The columns are free text written for a reader, not for a parser, so each
    rule here exists because of rows that break the obvious version of it.
    """

    def unit(self, **columns):
        return mudfinder.creature_to_unit(columns)

    def test_the_name_carries_over(self):
        assert self.unit(Name="Dire Ape")["charName"] == "Dire Ape"

    def test_a_creature_with_no_name_still_builds(self):
        assert self.unit()["charName"] == "Creature"

    def test_hp_is_a_number(self):
        assert self.unit(Name="x", HP="30")["HP"] == 30

    def test_hp_is_never_zero(self):
        """Four rows carry a fractional hp, and a creature that arrives already
        dead is no use to anyone."""
        assert self.unit(Name="Flying Fox", HP="0.5")["HP"] == 1

    def test_max_hp_matches(self):
        assert self.unit(Name="x", HP="30")["maxHP"] == 30

    @pytest.mark.parametrize("init,expected", [
        ("2", 2), ("+6", 6), ("-1", -1), ("0", 0),
        ("+8M", 8),
        ("+4 (+8 when climbing trees)", 4),
        ("+1/-19, dual initiative", 1),
        ("", 0), ("special", 0),
    ])
    def test_the_initiative_bonus(self, init, expected):
        assert mudfinder.creature_initiative_bonus({"Init": init}) == expected

    @pytest.mark.parametrize("size,expected", [
        ("Fine", "small"), ("Diminutive", "small"), ("Tiny", "small"),
        ("Small", "small"), ("Medium", "medium"), ("Large", "large"),
        ("Huge", "large"), ("Gargantuan", "large"), ("Colossal", "large"),
        ("", "medium"), ("nonsense", "medium"),
    ])
    def test_size_collapses_to_the_three_the_map_draws(self, size, expected):
        """Huge and above share the Large footprint, which is all the app
        models -- a known loss rather than a surprise."""
        assert self.unit(Name="x", Size=size)["size"] == expected

    def test_darkvision_and_low_light_come_from_senses(self):
        unit = self.unit(Name="x", Senses="darkvision 60 ft., low-light vision; Perception +4")
        assert unit["darkvision"] is True
        assert unit["lowLight"] is True

    def test_one_sense_without_the_other(self):
        unit = self.unit(Name="x", Senses="low-light vision, scent; Perception +8")
        assert unit["darkvision"] is False
        assert unit["lowLight"] is True

    def test_no_senses_at_all(self):
        unit = self.unit(Name="x")
        assert unit["darkvision"] is False
        assert unit["lowLight"] is False

    @pytest.mark.parametrize("senses,expected", [
        ("darkvision 60 ft.; Perception +26", 26),
        ("Perception -1", -1),
        ("Perception +4 (+11 urban)", 4),
    ])
    def test_perception_comes_out_of_senses(self, senses, expected):
        assert self.unit(Name="x", Senses=senses)["perception"] == expected

    def test_no_perception_is_left_to_the_default(self):
        assert "perception" not in self.unit(Name="x", Senses="blindsense 30 ft.")

    @pytest.mark.parametrize("speed,expected", [
        ("30 ft.", 30), ("20 ft., fly 30 ft. (poor)", 20),
        ("10 ft., swim 60 ft.", 10), ("25 feet", 25),
        ("", 30), ("immobile", 30),
    ])
    def test_movement_speed(self, speed, expected):
        assert self.unit(Name="x", Speed=speed)["movementSpeed"] == expected

    def test_ability_scores(self):
        unit = self.unit(Name="x", AbilityScores="Str 11, Dex 15, Con 14, Int 2, Wis 11, Cha 10")
        assert (unit["STR"], unit["DEX"], unit["CON"]) == ("11", "15", "14")
        assert (unit["INT"], unit["WIS"], unit["CHA"]) == ("2", "11", "10")

    def test_ability_scores_with_stray_spacing(self):
        """Seventy-odd rows have a double space in there."""
        unit = self.unit(Name="x", AbilityScores="Str 20, Dex 23, Con 21, Int 14,  Wis 18, Cha 21")
        assert unit["WIS"] == "18"

    def test_a_missing_ability_score_is_blank(self):
        """A construct has no Constitution at all, written as a dash."""
        assert self.unit(Name="x", AbilityScores="Str 20, Dex 13, Con -, Int -")["CON"] == ""

    def test_no_ability_scores_at_all(self):
        assert "STR" not in self.unit(Name="x")

    @pytest.mark.parametrize("alignment,expected", [
        ("CE", "CE"), ("N", "N"), ("LG", "LG"),
        ("", "N"), ("any alignment", "N"),
    ])
    def test_alignment(self, alignment, expected):
        assert self.unit(Name="x", Alignment=alignment)["alignment"] == expected

    def test_the_unit_type_is_a_role_not_a_creature_type(self):
        """Unit.type is checked against "player" across the server. A creature
        whose type became "humanoid" would be neither one thing nor the other."""
        assert self.unit(Name="x", Type="humanoid")["type"] == "Mob"

    def test_abilities_are_gathered(self):
        unit = self.unit(Name="x", SpecialAbilities="Rend", SpecialAttacks="Grab", SQ="amphibious")
        assert unit["permanentAbilities"] == "Rend\n\nGrab\n\namphibious"

    def test_abilities_are_capped(self):
        """They are copied onto every creature added and go out with every
        update, so the longest statblock in the table is not carried whole."""
        unit = self.unit(Name="x", SpecialAbilities="a" * 9000)
        assert len(unit["permanentAbilities"]) <= mudfinder.MAX_PERMANENT_ABILITIES + 1

    def test_a_mapped_unit_survives_being_saved(self):
        """Unit.to_json is a hand-written key list, so a field it does not name
        is lost the moment the game is saved."""
        mapped = self.unit(Name="Dire Ape", HP="30", Size="Large", Init="2",
                           Senses="low-light vision; Perception +8",
                           AbilityScores="Str 19, Dex 15, Con 16, Int 2, Wis 12, Cha 7",
                           Alignment="N", Speed="30 ft.", SpecialAbilities="rend")
        saved = Unit(mapped).to_json()
        assert all(key in saved for key in mapped)


class TestShippedCreatureDatabase:
    """Properties of the file that ships, so a bad rebuild fails here."""

    def creatures(self):
        return sqlite3.connect("mudfinder.sql")

    def test_both_datasets_are_present(self):
        db = self.creatures()
        count = db.execute("select count(*) from creatures").fetchone()[0]
        assert count > 10000

    def test_every_creature_has_a_normalised_type(self):
        db = self.creatures()
        assert db.execute(
            "select count(*) from creatures where coalesce(TypeNorm,'') = ''").fetchone()[0] == 0

    def test_the_normalised_types_are_the_known_ones(self):
        db = self.creatures()
        found = {row[0] for row in db.execute("select distinct TypeNorm from creatures")}
        assert found <= set(mudfinder.CREATURE_TYPES)

    def test_the_dropped_column_is_gone(self):
        db = self.creatures()
        columns = [row[1] for row in db.execute("PRAGMA table_info(creatures)")]
        assert "FullText" not in columns

    def test_the_bundled_bestiary_kept_its_prose(self):
        """The merge rebuilds the table, and dropping the wrong column would
        take every creature's description with it."""
        db = self.creatures()
        row = db.execute("select Description from creatures where Name = 'Dire Ape'").fetchone()
        assert row and "gigantopithecus" in row[0]

    def test_a_creature_is_not_in_there_twice(self):
        """Keying the merge on anything but the name imported a second Goblin,
        identical to the first, for the GM to choose between."""
        db = self.creatures()
        assert db.execute("select count(*) from creatures where lower(Name) = 'goblin'").fetchone()[0] == 1

    def test_the_spells_survived_the_rebuild(self):
        db = self.creatures()
        assert db.execute("select count(*) from spells").fetchone()[0] > 2000


class TestPuttingTheLineBreaksBack:
    """The bestiary columns run their entries together.

    Special abilities arrive as one string with a double space between them --
    "Appraising Sight (Ex) ...free action.  Aura Sight (Su) ..." -- because the
    structure only ever existed in the HTML statblock, which the import drops
    for being thirteen megabytes of restating the other columns. Each entry
    opens distinctively enough to put the breaks back.
    """

    def test_abilities_are_split(self):
        text = ("Appraising Sight (Ex) An occult dragon can appraise items.  "
                "Aura Sight (Su) An old dragon sees all objects.  "
                "Change Shape (Su) A juvenile dragon can assume any form.")
        assert mudfinder.split_abilities(text).split("\n") == [
            "Appraising Sight (Ex) An occult dragon can appraise items.",
            "Aura Sight (Su) An old dragon sees all objects.",
            "Change Shape (Su) A juvenile dragon can assume any form.",
        ]

    def test_a_single_ability_is_left_alone(self):
        assert mudfinder.split_abilities("Rend (Ex) Two claws hit.") == "Rend (Ex) Two claws hit."

    def test_nothing_is_nothing(self):
        assert mudfinder.split_abilities("") == ""
        assert mudfinder.split_abilities(None) == ""

    def test_a_double_space_mid_sentence_is_not_a_break(self):
        """The break is the gap plus an ability name, not the gap alone."""
        assert "\n" not in mudfinder.split_abilities("Rend (Ex) Two claws hit.  Then again.")

    def test_spell_lists_split_by_level(self):
        text = ("Psychic Spells Known (CL 7th; concentration +12)  "
                "3rd (5/day)-gaseous form  2nd (7/day)-hideous laughter (DC 15)  "
                "0 (at-will)-detect magic")
        assert mudfinder.split_abilities(text, mudfinder.SPELL_LEVEL_BOUNDARY).split("\n") == [
            "Psychic Spells Known (CL 7th; concentration +12)",
            "3rd (5/day)-gaseous form",
            "2nd (7/day)-hideous laughter (DC 15)",
            "0 (at-will)-detect magic",
        ]

    def test_the_unit_gets_its_abilities_a_line_at_a_time(self):
        unit = mudfinder.creature_to_unit({
            "Name": "Adult Occult Dragon",
            "SpecialAbilities": "Aura Sight (Su) Sees auras.  Item Mastery (Su) Emulates.",
        })
        assert unit["permanentAbilities"] == "Aura Sight (Su) Sees auras.\nItem Mastery (Su) Emulates."

    def test_every_column_that_runs_together_is_covered(self):
        assert set(mudfinder.RUN_TOGETHER_COLUMNS) == {
            "SpecialAbilities", "SpecialAttacks", "SpellsKnown",
            "SpellsPrepared", "SpellLikeAbilities"}

    def test_the_shipped_data_actually_splits(self):
        """Guards the patterns against a future rebuild whose columns are
        punctuated differently."""
        db = sqlite3.connect("mudfinder.sql")
        row = db.execute(
            "select SpecialAbilities from creatures where Name like 'Adult Occult Dragon%'"
        ).fetchone()
        assert row and mudfinder.split_abilities(row[0]).count("\n") >= 5


class TestAbilityBoundariesThatAreNotDoubleSpaces:
    """How the abilities column punctuates the gap between entries varies.

    Anchoring the split on a double space caught most of it and missed the
    rows that separate with a single space after a closing bracket, which
    left creatures like the Earth Elemental Construct as one paragraph.
    """

    def test_a_single_space_after_a_bracket_is_a_break(self):
        text = ("Earth Mastery (Ex) Gains a bonus. (These modifiers are not included.) "
                "Immunity to Magic (Ex) Immune to any spell.")
        assert mudfinder.split_abilities(text).split("\n") == [
            "Earth Mastery (Ex) Gains a bonus. (These modifiers are not included.)",
            "Immunity to Magic (Ex) Immune to any spell.",
        ]

    def test_a_single_space_after_a_full_stop_is_a_break(self):
        text = "Rend (Ex) Two claws hit. Pound (Ex) Slams an opponent."
        assert mudfinder.split_abilities(text).count("\n") == 1

    def test_a_tag_mid_sentence_is_not_a_break(self):
        """The break needs a finished sentence in front of it, or every
        parenthesised tag in a description would start a new ability."""
        text = "Rend (Ex) If both claws hit the same Target (Ex) is not a new ability."
        assert "\n" not in mudfinder.split_abilities(text)

    def test_the_shipped_construct_splits_into_its_three(self):
        db = sqlite3.connect("mudfinder.sql")
        row = db.execute(
            "select SpecialAbilities from creatures where Name = 'Earth Elemental Construct'"
        ).fetchone()
        assert row and len(mudfinder.split_abilities(row[0]).split("\n")) == 3


class TestStrippingTheStatblockMarkup:
    """The import takes the markup off a FullText statblock.

    Not a security boundary -- the result is stored as text and rendered with
    textContent, never as markup -- but a pattern that misses a closing tag
    leaves it behind in the prose, so it is written properly.
    """

    def strip(self, html_text):
        import tools.import_creatures as importer
        return importer.statblock_text(html_text)

    def test_the_stylesheet_link_goes(self):
        assert self.strip('<link rel="stylesheet" href="PF.css">Kept') == "Kept"

    def test_a_script_and_its_contents_go(self):
        assert self.strip("<script>alert(1)</script>Kept") == "Kept"

    @pytest.mark.parametrize("closing", [
        "</script>", "</script >", "</SCRIPT\t>", "</ script>",
        "</script\n foo=bar>",
    ])
    def test_an_end_tag_is_matched_as_html_defines_it(self, closing):
        """Whitespace is allowed after the slash and anything up to the bracket
        is ignored, so all of these are end tags. A pattern anchored on a bare
        "</script>" leaves the rest sitting in the text."""
        assert self.strip("<script>bad()" + closing + "Kept") == "Kept"

    def test_a_style_block_goes_the_same_way(self):
        assert self.strip("<style >p{color:red}</style >Kept") == "Kept"

    def test_block_tags_become_line_breaks(self):
        assert self.strip("<h5>First</h5><h5>Second</h5>") == "First\nSecond"

    def test_entities_are_unescaped(self):
        assert self.strip("<p>Bell &amp; Candle</p>").startswith("Bell & Candle")

    def test_the_shipped_descriptions_carry_no_markup(self):
        db = sqlite3.connect("mudfinder.sql")
        for pattern in ("%<script%", "%</script%", "%<style%", "%<link%"):
            assert db.execute(
                "select count(*) from creatures where Description like ?",
                (pattern,)).fetchone()[0] == 0


class TestParsingAttacks:
    """Turning a bestiary Melee or Ranged column into attacks.

    Every case here is a string that actually occurs in the shipped table. The
    danger in this parser is not failing to read something -- it is reading it
    confidently and wrongly, because a bad bonus changes the game quietly.
    """

    def names(self, text):
        return [(a["name"], a["attack"], a["damage"]) for a in mudfinder.parse_attacks(text)]

    def test_a_single_attack(self):
        assert self.names("bite +6 (1d6+4)") == [("bite", "+6", "1d6+4")]

    def test_several_attacks(self):
        assert self.names("bite +6 (1d6+4), 2 claws +6 (1d4+4)") == [
            ("bite", "+6", "1d6+4"), ("2 claws", "+6", "1d4+4")]

    def test_a_count_is_kept_with_the_name(self):
        """The seven-item weapon list has no room for it, and it reads the way
        the statblock does."""
        assert mudfinder.parse_attacks("2 claws +6 (1d4+4)")[0]["name"] == "2 claws"

    def test_iteratives(self):
        assert self.names("mwk longsword +4/-1 (1d8/19-20)") == [
            ("mwk longsword", "+4/-1", "1d8/19-20")]

    def test_the_crit_range_is_pulled_out(self):
        assert mudfinder.parse_attacks("short sword +2 (1d4/19-20)")[0]["crit"] == "19-20"

    def test_the_crit_multiplier_is_pulled_out(self):
        assert mudfinder.parse_attacks("short bow +4 (1d4/x3)")[0]["crit"] == "x3"

    def test_both_together(self):
        assert mudfinder.parse_attacks("katana +11 (1d8+1/18-20/x4)")[0]["crit"] == "18-20/x4"

    def test_the_older_melee_keyword_is_a_qualifier(self):
        assert self.names("gore +4 melee (1d8+4)") == [("gore", "+4", "1d8+4")]

    # The four rulings on the entries a first pass could not read.

    def test_jandri_a_missing_bonus_means_zero(self):
        """"club (1d6-1)" is a real attack whose bonus was never written down.
        Dropping it would lose the attack; a +0 is what it means."""
        assert self.names("club (1d6-1)") == [("club", "+0", "1d6-1")]

    def test_bipedal_a_missing_bonus_with_a_count(self):
        assert self.names("2 claws (1d4)") == [("2 claws", "+0", "1d4")]

    def test_hungry_fog_touch_names_the_attack(self):
        """In "+5 touch (6d6...)" the word touch says the attack resolves
        against touch AC and is also the only name it has."""
        assert self.names("+5 touch (6d6 negative energy)") == [
            ("touch", "+5", "6d6 negative energy")]

    def test_king_elmander_a_lone_leading_bonus_is_the_to_hit(self):
        """The statblock is wrong -- the sword is unenchanted and +3 is what he
        swings at. Reading it as an enhancement bonus gets him exactly
        backwards."""
        assert self.names("+3 mithral short sword (1d4+2/19-20)") == [
            ("mithral short sword", "+3", "1d4+2/19-20")]

    def test_a_leading_bonus_beside_a_to_hit_stays_in_the_name(self):
        """The other half of the rule, and the reason it is a rule rather than
        a fix for one creature."""
        assert self.names("+2 naginata** +22/+17/+12 (2d6+15/x4)") == [
            ("+2 naginata**", "+22/+17/+12", "2d6+15/x4")]

    def test_poltergeist_is_listed_but_not_rollable(self):
        attack = mudfinder.parse_attacks("telekinesis (see below)")[0]
        assert attack["name"] == "telekinesis"
        assert attack["rollable"] is False

    def test_the_statue_of_wishes_is_listed_too(self):
        assert mudfinder.parse_attacks("+0 (no physical attack)")[0]["rollable"] is False

    def test_a_swarm_has_damage_and_no_attack_roll(self):
        """Giving it the +0 that a missing bonus otherwise means would be
        inventing a number the creature does not have."""
        attack = mudfinder.parse_attacks("swarm (2d6 plus poison)")[0]
        assert attack["rollable"] is True
        assert attack["attacks"] is False

    def test_a_troop_likewise(self):
        assert mudfinder.parse_attacks("troop (3d6+5)")[0]["attacks"] is False

    def test_an_aside_in_the_name_is_unwrapped(self):
        """Read as damage, the brackets swallow the name and the attack ends up
        called "1d4+7"."""
        assert self.names("binding contract (whip) +20/+15/+10 (1d4+7 plus bleed)") == [
            ("binding contract whip", "+20/+15/+10", "1d4+7 plus bleed")]

    def test_an_aside_does_not_become_its_own_attack(self):
        assert len(mudfinder.parse_attacks(
            "Passion's Edge (+2 falchion) +14/+9 (2d4+8/18-20)")) == 1

    def test_none_yields_nothing(self):
        assert mudfinder.parse_attacks("none") == []

    def test_nothing_yields_nothing(self):
        assert mudfinder.parse_attacks("") == []
        assert mudfinder.parse_attacks(None) == []


class TestHowManySwings:
    """One press of the button is a full attack, not a single die."""

    @pytest.mark.parametrize("name,to_hit,expected", [
        ("bite", "+6", 1),
        ("2 claws", "+6", 2),
        ("6 tentacles", "+20", 6),
        ("longsword", "+18/+13/+8", 3),
        ("2 claws", "+18/+13", 4),
        ("bite", "", 1),
    ])
    def test_count_times_iteratives(self, name, to_hit, expected):
        assert mudfinder.attack_swings(name, to_hit) == expected


class TestCreatureWeapons:
    """What a picked creature arrives carrying."""

    def creature(self, name):
        db = sqlite3.connect("mudfinder.sql")
        db.row_factory = sqlite3.Row
        row = db.execute(
            "select * from creatures where Name = ? and coalesce(Melee,'') != '' limit 1",
            (name,)).fetchone()
        return dict(row)

    def test_a_dire_ape_has_its_two_attacks(self):
        weapons = mudfinder.creature_weapons(self.creature("Dire Ape"))
        assert [w[0] for w in weapons] == ["bite", "2 claws"]

    def test_the_entries_are_the_shape_unit_weapons_holds(self):
        """Seven items, positional, the same list a player's longsword is in."""
        assert all(len(w) == 7 for w in mudfinder.creature_weapons(self.creature("Dire Ape")))

    def test_ranged_attacks_come_too(self):
        weapons = mudfinder.creature_weapons(self.creature("Goblin"))
        assert ("short bow", "ranged") in [(w[0], w[4]) for w in weapons]

    def test_melee_is_marked_as_melee(self):
        weapons = mudfinder.creature_weapons(self.creature("Goblin"))
        assert ("short sword", "melee") in [(w[0], w[4]) for w in weapons]

    def test_a_picked_creature_carries_them_onto_the_unit(self):
        unit = mudfinder.creature_to_unit(self.creature("Dire Ape"))
        assert [w[0] for w in unit["weapons"]] == ["bite", "2 claws"]

    def test_they_survive_being_saved(self):
        unit = mudfinder.creature_to_unit(self.creature("Dire Ape"))
        assert Unit(unit).to_json()["weapons"] == unit["weapons"]

    def test_a_creature_with_no_attacks_gets_an_empty_list(self):
        assert mudfinder.creature_weapons({"Name": "x"}) == []


class TestParsingCastings:
    """The things a creature can cast a limited number of times.

    At-will and constant entries are deliberately absent: they are in the
    statblock the picker shows and never need a counter.
    """

    def parse(self, text):
        return [(c["label"], c["spells"], c["uses"]) for c in mudfinder.parse_castings(text)]

    def test_a_per_day_group_is_a_shared_pool(self):
        assert self.parse("Spell-Like Abilities (CL 16th) 3/day-dominate monster (DC 22)") == [
            ("3/day", "dominate monster (DC 22)", 3)]

    def test_a_pool_covers_every_spell_in_it(self):
        """Four castings drawn from the two, not four of each."""
        assert self.parse(
            "Spells Known (CL 9th) 4th (4/day)-charm monster (DC 17), freedom of movement") == [
            ("4th (4/day)", "charm monster (DC 17), freedom of movement", 4)]

    def test_a_prepared_level_is_one_casting_per_spell(self):
        assert self.parse(
            "Spells Prepared (CL 16th) 8th-earthquake (DC 25), fire storm (DC 25)") == [
            ("8th", "earthquake (DC 25)", 1), ("8th", "fire storm (DC 25)", 1)]

    def test_a_prepared_spell_can_be_prepared_more_than_once(self):
        assert self.parse(
            "Spells Prepared (CL 16th) 1st-bless (2), cure light wounds (4), shield of faith") == [
            ("1st", "bless (2)", 2), ("1st", "cure light wounds (4)", 4),
            ("1st", "shield of faith", 1)]

    def test_a_semicolon_separates_a_count_too(self):
        """The table uses both punctuations, and matching only the comma
        undercounts seventeen prepared spells."""
        assert self.parse("Spells Prepared (CL 20th) 9th-implosion (2; DC 28)") == [
            ("9th", "implosion (2; DC 28)", 2)]

    def test_a_note_after_the_count_is_still_a_count(self):
        assert self.parse("Spells Prepared (CL 9th) 3rd-remove disease (4; already cast)") == [
            ("3rd", "remove disease (4; already cast)", 4)]

    def test_damage_dice_in_the_name_are_not_a_count(self):
        """"(2d6)" begins with a digit and is not two castings."""
        assert self.parse("Spells Prepared (CL 5th) 2nd-acid arrow (2d6)") == [
            ("2nd", "acid arrow (2d6)", 1)]

    def test_a_dc_is_not_a_count(self):
        """The pair is the test. A parser that reads every bracket as a count
        passes the first of these and hands the second twenty-two castings."""
        assert self.parse("Spells Prepared (CL 16th) 5th-dispel evil (2, DC 22)") == [
            ("5th", "dispel evil (2, DC 22)", 2)]
        assert self.parse("Spells Prepared (CL 16th) 5th-plane shift (DC 22)") == [
            ("5th", "plane shift (DC 22)", 1)]

    def test_at_will_is_not_tracked(self):
        assert mudfinder.parse_castings(
            "Spell-Like Abilities (CL 13th) At will-aid, continual flame") == []

    def test_constant_is_not_tracked(self):
        assert mudfinder.parse_castings(
            "Spell-Like Abilities (CL 16th) Constant-detect evil, true seeing") == []

    def test_cantrips_at_will_are_not_tracked(self):
        assert mudfinder.parse_castings(
            "Spells Known (CL 3rd) 0 (at will)-dancing lights, detect magic") == []

    def test_the_limited_ones_survive_beside_the_unlimited(self):
        castings = self.parse(
            "Spell-Like Abilities (CL 16th) At will-hypnotic pattern (DC 15) "
            "3/day-dominate monster (DC 22)")
        assert castings == [("3/day", "dominate monster (DC 22)", 3)]

    def test_uses_start_at_the_daily_number(self):
        casting = mudfinder.parse_castings(
            "Spell-Like Abilities (CL 1st) 7/day-cure light wounds")[0]
        assert casting["uses"] == casting["daily"] == 7

    def test_nothing_yields_nothing(self):
        assert mudfinder.parse_castings("") == []
        assert mudfinder.parse_castings(None) == []


class TestSplittingASpellList:
    """Commas inside brackets are not separators."""

    def test_a_plain_list(self):
        assert mudfinder.split_spell_list("bless, command, shield") == [
            "bless", "command", "shield"]

    def test_a_comma_inside_brackets_holds_the_spell_together(self):
        assert mudfinder.split_spell_list("dispel evil (2, DC 22), plane shift (DC 22)") == [
            "dispel evil (2, DC 22)", "plane shift (DC 22)"]

    def test_nothing_yields_nothing(self):
        assert mudfinder.split_spell_list("") == []


class TestCreatureCastings:
    def creature(self, name):
        db = sqlite3.connect("mudfinder.sql")
        db.row_factory = sqlite3.Row
        return dict(db.execute(
            "select rowid as id, * from creatures where Name = ? limit 1", (name,)).fetchone())

    def test_an_aboleth_has_its_one_limited_casting(self):
        castings = mudfinder.creature_castings(self.creature("Aboleth"))
        assert len(castings) == 1
        assert castings[0]["spells"] == "dominate monster (DC 22)"

    def test_a_planetar_has_a_great_many(self):
        assert len(mudfinder.creature_castings(self.creature("Planetar"))) == 30

    def test_a_creature_that_casts_nothing_has_none(self):
        assert mudfinder.creature_castings(self.creature("Dire Ape")) == []

    def test_a_picked_creature_carries_them(self):
        unit = mudfinder.creature_to_unit(self.creature("Aboleth"))
        assert unit["castings"][0]["uses"] == 3

    def test_they_survive_being_saved(self):
        unit = mudfinder.creature_to_unit(self.creature("Aboleth"))
        assert Unit(unit).to_json()["castings"] == unit["castings"]


class TestRememberingTheCreature:
    """A unit keeps the row it came from, so its full statblock can be looked
    up later. The unit carries only the mapped fields; without this there is
    nothing to look the rest up by."""

    def test_a_picked_creature_records_its_id(self):
        db = sqlite3.connect("mudfinder.sql")
        db.row_factory = sqlite3.Row
        creature = dict(db.execute(
            "select rowid as id, * from creatures where Name = 'Aboleth' limit 1").fetchone())
        assert mudfinder.creature_to_unit(creature)["creatureId"] == creature["id"]

    def test_a_hand_made_unit_has_none(self):
        assert make_unit().creatureId is None

    def test_it_survives_being_saved(self):
        assert Unit({"charName": "x", "creatureId": 412}).to_json()["creatureId"] == 412

# The design language lives in docs/design.md. Its central claim is that every
# colour in the app's chrome comes from the token block at the top of the
# stylesheet, so these read the stylesheet rather than the browser.
STYLESHEET = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          "static", "css", "mudfinder.css")

COLOUR_LITERAL = re.compile(
    r"#[0-9a-fA-F]{3,8}\b"
    r"|\brgba?\([^)]*\)"
    r"|\b(?:white|black|lightgrey|lightgray|grey|gray|cornflowerblue|firebrick"
    r"|red|blue|green|silver|gold|tan|beige|ivory|wheat)\b")

# Chrome, as opposed to map artwork. A wall is drawn in ink the way the ink on a
# printed map is: it is the subject, not the frame around it, and design.md says
# so explicitly.
CHROME_RULES = ["button", "input", ".panel", ".panelHeading", ".formCard",
                ".tab", ".tabsDiv", ".chatText", ".fieldLabel", ".sectionHeading",
                "#linkDiv", "#mapTools", "#creaturePicker"]


def stylesheet():
    """The stylesheet with its comments taken out.

    Comments carry both braces and colour names -- the token block's own
    commentary explains what black hairlines used to look like -- so leaving
    them in makes every check below read the prose instead of the rules.
    """
    with open(STYLESHEET) as handle:
        return re.sub(r"/\*.*?\*/", "", handle.read(), flags=re.S)


def rule_body(css, selector):
    """The declarations of the first rule whose selector list starts with this."""
    for match in re.finditer(r"(^|\})\s*([^{}]+)\{([^{}]*)\}", css, re.M):
        selectors = [s.strip() for s in match.group(2).split(",")]
        if any(s == selector or s.startswith(selector + ":") for s in selectors):
            return match.group(3)
    raise AssertionError("no rule for %s" % selector)


class TestTheDesignTokens:
    def test_the_token_block_is_at_the_top(self):
        css = stylesheet()
        assert css.index(":root {") < css.index("html, body {")

    def test_every_token_the_spec_names_exists(self):
        css = stylesheet()
        root = rule_body(css, ":root")
        for token in ["--ink", "--ink-soft", "--ink-faint", "--paper",
                      "--paper-warm", "--desk", "--rule", "--rule-faint",
                      "--accent", "--accent-soft", "--danger", "--radius",
                      "--radius-panel", "--heading-tracking", "--desk-grain",
                      "--tab-wash", "--tab-wash-hover", "--shadow-lifted",
                      "--shadow-resting", "--gilt", "--desk-light",
                      "--cloth", "--cloth-weave"]:
            assert token + ":" in root, token

    def test_the_chrome_names_no_colour_of_its_own(self):
        """The one rule the spec actually enforces: a component that wants a
        shade adds a token rather than a hex code."""
        css = stylesheet()
        offenders = {}
        for selector in CHROME_RULES:
            found = COLOUR_LITERAL.findall(rule_body(css, selector))
            if found:
                offenders[selector] = found
        assert offenders == {}

    def test_the_statblock_draws_on_the_shared_tokens(self):
        """It is where the palette came from, so it must not keep a private
        copy that can drift from it."""
        block = rule_body(stylesheet(), ".statblock")
        assert "--sbInk: var(--ink)" in block
        assert "--sbRule: var(--rule)" in block

    def test_the_tab_bar_cannot_grow_past_forty_pixels(self):
        """Everything below it is laid out against calc(100% - 40px). A 41px bar
        pushed the map a pixel out of the window, which was enough to break the
        battlemap alignment drag."""
        bar = rule_body(stylesheet(), ".tabsDiv")
        assert "height:40px" in bar.replace(" ", "")
        assert "box-sizing: border-box" in bar

    def test_the_grain_and_the_rings_run_along_the_board(self):
        """Two of the four turbulences draw things that run *along* the timber
        -- the figure of the board and the growth rings -- and their whole job
        is being lopsided: frequent across it, barely varying down it. Even in
        both axes they are blobs, not grain."""
        freqs = grain_frequencies()
        for index in (BOARD, RINGS):
            across, down = freqs[index]
            assert across / down >= 10, (index, across, down)

    def test_the_wave_is_slow(self):
        """The wave through the grain has to play out over hundreds of pixels.
        In the tens it reads as fur, which is where two earlier attempts at
        this landed."""
        across, down = grain_frequencies()[WAVE]
        assert across < 0.01 and down < 0.01, (across, down)

    def test_the_light_is_not_painted_twice(self):
        """The desk's light and shade belongs to --desk-light. An earlier
        version modulated the timber for it as well, and the two together
        flattened the colour instead of deepening it."""
        root = rule_body(stylesheet(), ":root")
        assert "--desk-light" in root
        assert len(grain_frequencies()) == 3

    def test_the_rings_are_one_octave(self):
        """A growth ring is a single continuous line. Further octaves vary the
        noise *along* the ring as well as across it, and the discrete transfer
        that makes the line crisp turns that variation into a dashed one."""
        grain = urllib.parse.unquote(desk_grain())
        rings = grain[grain.index("<filter id='r'"):]
        assert re.search(r"numOctaves='1'", rings), rings[:200]

    def test_the_desk_is_planked(self):
        """A desk is boards, not one sheet."""
        assert len(seam_positions()) >= 5

    def test_the_boards_are_not_evenly_spaced(self):
        """Even spacing reads as tiling rather than as timber."""
        edges = [0] + seam_positions()
        widths = [b - a for a, b in zip(edges, edges[1:])]
        assert len(set(widths)) == len(widths), widths

    def test_each_board_carries_its_own_tone(self):
        """The cue that actually reads. A seam line on its own is lost among
        the growth rings, which are dark vertical lines too."""
        grain = urllib.parse.unquote(desk_grain())
        tinted = re.findall(r"<rect x='\d+' width='\d+' height='1000' "
                            r"fill='(#[0-9a-f]{6})' opacity='([0-9.]+)'", grain)
        assert len(tinted) == len(seam_positions()) + 1, tinted
        assert len(set(tinted)) > 1, tinted

    def test_the_desk_has_knots(self):
        assert len(knot_positions()) >= 12

    def test_no_knot_sits_across_a_seam(self):
        """Knots are in boards, not in the join between two of them."""
        seams = seam_positions()
        for x, y in knot_positions():
            assert all(abs(x - seam) > 30 for seam in seams), (x, y)

    def test_the_knots_are_not_spread_evenly(self):
        """Some boards are clear and some are full of them. Three per board is
        a grid, which is what the first placement looked like."""
        seams = seam_positions()
        counts = []
        edges = [0] + seams + [1400]
        for a, b in zip(edges, edges[1:]):
            counts.append(sum(1 for x, _ in knot_positions() if a <= x < b))
        assert max(counts) - min(counts) >= 2, counts

    def test_the_rings_are_cut_rather_than_shaded(self):
        """discrete, not table. A linear table can only give a soft gradient;
        an incised line needs a hard edge."""
        grain = urllib.parse.unquote(desk_grain())
        rings = grain[grain.index("<filter id='r'"):]
        assert "type='discrete'" in rings
        assert "type='table'" not in rings

    def test_the_desk_fetches_nothing(self):
        """It is drawn, not downloaded."""
        grain = urllib.parse.unquote(desk_grain())
        assert "data:image/svg+xml" in grain
        # The SVG namespace is a name, not somewhere the browser goes.
        assert re.sub(r"http://www\.w3\.org\S*", "", grain).count("http") == 0


# Which turbulence is which, in the order the filter declares them.
BOARD, WAVE, RINGS = 0, 1, 2


def grain_frequencies():
    """Every turbulence in the desk, as (across, down) pairs, in filter order."""
    grain = urllib.parse.unquote(desk_grain())
    found = re.findall(r"baseFrequency='([0-9.]+)\s+([0-9.]+)'", grain)
    assert len(found) == 3, found
    return [(float(a), float(b)) for a, b in found]


def seam_positions():
    """The dark centre of each board join."""
    grain = urllib.parse.unquote(desk_grain())
    found = re.findall(r"<rect x='([0-9.]+)' width='3.0' height='1000' "
                       r"fill='#0d0602'", grain)
    return [float(x) for x in found]


def knot_positions():
    grain = urllib.parse.unquote(desk_grain())
    found = re.findall(r"<g transform='translate\((\d+),(\d+)\)", grain)
    return [(int(x), int(y)) for x, y in found]


def desk_grain():
    root = rule_body(stylesheet(), ":root")
    start = root.index("--desk-grain")
    return root[start:root.index(";", start)]


class TestNothingIsFetchedFromAnywhere:
    """The player page used to pull a font from fontlibrary.org on every load,
    which made the page depend on a third party and fail when offline. Nothing
    the browser loads may name an external host."""

    def files(self):
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        found = []
        for folder in [os.path.join(here, "templates"),
                       os.path.join(here, "static", "css"),
                       os.path.join(here, "static", "js")]:
            for name in sorted(os.listdir(folder)):
                if name.endswith((".html", ".css", ".js")):
                    found.append(os.path.join(folder, name))
        return found

    def test_no_stylesheet_or_page_names_an_external_host(self):
        offenders = {}
        for path in self.files():
            with open(path, encoding="utf-8", errors="replace") as handle:
                body = handle.read()
            # Bare "http" inside a comment or an XML namespace is not a fetch;
            # a URL the browser would go and get is.
            hits = re.findall(r"""(?:src|href|url)\s*[=(]\s*["']?(https?://[^"')\s]+)""",
                              body, re.I)
            hits = [h for h in hits if "www.w3.org" not in h]
            if hits:
                offenders[os.path.basename(path)] = hits
        assert offenders == {}
