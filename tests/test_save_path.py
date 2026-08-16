"""Tests for room id validation.

A room id becomes a filename under saves/. It is generated server-side, but it
also arrives from the client on every socket event and from uploaded save
files, so check_room() would otherwise read and write anywhere on disk.
"""

import json
import os

import pytest

import mudfinder
from mudfinder import check_room, save_path

TRAVERSALS = [
    "../secrets",
    "../../etc/passwd",
    "..%2f..%2fetc",
    "foo/bar",
    "foo\\bar",
    "/etc/passwd",
    "/absolute",
    ".",
    "..",
    "",
    "a" * 65,
    "room name with spaces",
    "room;rm -rf",
    "room\x00null",
    "‮",
]


class TestSavePath:
    @pytest.mark.parametrize("room", TRAVERSALS)
    def test_unsafe_ids_have_no_save_path(self, room):
        assert save_path(room) is None

    @pytest.mark.parametrize("room", [
        "abc123",
        "A1b2C3",
        "with-dash",
        "with_underscore",
        "0" * 64,
        "b4f0e1c2d3a4",
    ])
    def test_safe_ids_resolve_under_saves(self, room):
        resolved = save_path(room)
        assert resolved is not None
        assert os.path.dirname(resolved) == "saves"
        assert resolved.endswith(room + ".json")

    def test_a_real_session_id_is_accepted(self):
        """Room ids are engine.io session ids, which are plain hex."""
        assert save_path("f07eae34366c42b38d166039878c40af") is not None

    def test_non_string_ids_are_rejected(self):
        assert save_path(None) is None
        assert save_path(42) is None
        assert save_path(["a"]) is None


class TestCheckRoom:
    @pytest.mark.parametrize("room", TRAVERSALS)
    def test_traversal_ids_are_not_rooms(self, room):
        assert check_room(room) is False

    def test_a_json_file_outside_saves_is_not_loaded(self, tmp_path):
        """The actual exploit: load any .json on disk as a live game."""
        outside = tmp_path / "loot.json"
        outside.write_text(json.dumps({
            "name": "Someone else's campaign", "gmKey": "stolen",
            "inInit": False, "initiativeCount": 0, "roundCount": 0,
            "unitList": [], "lore": [], "savedEncounters": {},
            "mapData": {"mapArray": [[0]]},
        }))
        room = os.path.relpath(str(outside), "saves")[: -len(".json")]

        assert check_room(room) is False
        assert room not in mudfinder.ROOMS

    def test_an_unknown_but_well_formed_id_is_simply_absent(self):
        assert check_room("neverseenbefore") is False


class TestUpload:
    def test_an_uploaded_save_with_a_traversal_room_is_refused(self, http):
        payload = json.dumps({
            "room": "../../../tmp/pwned", "gmKey": "k", "name": "Evil",
            "inInit": False, "initiativeCount": 0, "roundCount": 0,
            "unitList": [], "lore": [], "savedEncounters": {},
            "mapData": {"mapArray": [[0]]},
        }).encode()
        response = http.post(
            "/upload.html",
            data={"file": (__import__("io").BytesIO(payload), "save.json")},
            content_type="multipart/form-data",
        )
        assert response.status_code == 400
        assert "../../../tmp/pwned" not in mudfinder.ROOMS
