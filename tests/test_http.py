"""Tests for the plain HTTP routes."""

import json

import pytest

import mudfinder
from helpers import GM_KEY, make_player


class TestPages:
    @pytest.mark.parametrize("route", ["/", "/player.html", "/spectator.html", "/gm.html"])
    def test_page_renders(self, http, route):
        assert http.get(route).status_code == 200

    def test_index_offers_game_creation(self, http):
        assert b"Create Game" in http.get("/").data

    def test_gm_page_loads_its_script(self, http):
        assert b"gm.js" in http.get("/gm.html").data

    def test_unknown_route_is_a_404(self, http):
        assert http.get("/definitely-not-a-page").status_code == 404


class TestStatic:
    @pytest.mark.parametrize("asset", [
        "/static/js/socket.io.js",
        "/static/js/shared.js",
        "/static/js/gm.js",
        "/static/js/player.js",
        "/static/css/mudfinder.css",
    ])
    def test_asset_is_served(self, http, asset):
        assert http.get(asset).status_code == 200

    def test_vendored_socket_io_client_is_version_4(self, http):
        """The server dependencies have to match this client's protocol.

        Socket.IO 4.x speaks Engine.IO protocol 4, which needs
        python-engineio 4.x / Flask-SocketIO 5.x. If someone changes the
        vendored client, this fails as a reminder that requirements.txt has to
        move with it.
        """
        assert b"Socket.IO v4" in http.get("/static/js/socket.io.js").data[:200]

    def test_the_server_speaks_the_same_protocol_as_the_client(self):
        """The pairing this whole pinning exercise is about."""
        from importlib.metadata import version

        assert int(version("python-socketio").split(".")[0]) >= 5
        assert int(version("python-engineio").split(".")[0]) >= 4


class TestDownload:
    def test_gm_can_download_a_save(self, http, make_session):
        session = make_session(room="dl-room")
        session.unitList.append(make_player())
        session.playerList["Aria"] = session.unitList[-1]

        response = http.get("/download.html?room=dl-room&gmKey=%s" % GM_KEY)
        assert response.status_code == 200
        assert json.loads(response.data)["name"] == "Test Game"

    def test_download_is_sent_as_an_attachment(self, http, make_session):
        make_session(room="dl-room")
        response = http.get("/download.html?room=dl-room&gmKey=%s" % GM_KEY)
        assert "attachment" in response.headers["Content-disposition"]

    def test_saved_units_are_included(self, http, make_session):
        session = make_session(room="dl-room")
        session.unitList.append(make_player())
        session.playerList["Aria"] = session.unitList[-1]
        blob = json.loads(http.get("/download.html?room=dl-room&gmKey=%s" % GM_KEY).data)
        assert [u["charName"] for u in blob["unitList"]] == ["Aria"]

    def test_wrong_gm_key_is_refused(self, http, make_session):
        make_session(room="dl-room")
        response = http.get("/download.html?room=dl-room&gmKey=not-the-key")
        assert response.status_code == 404


class TestGetImage:
    def test_image_is_returned(self, http, make_session):
        session = make_session(room="img-room")
        # base64 for the bytes b"hello"
        session.images["abc"] = "aGVsbG8="
        response = http.get("/get_image.html?room=img-room&id=abc")
        assert response.status_code == 200
        assert response.data == b"hello"


class TestMissingResources:
    """Unknown rooms and ids are 404s, not 500s.

    A bad gmKey answers exactly like a missing room, so the endpoint cannot be
    used to probe which rooms exist.
    """

    def test_download_for_an_unknown_room_is_a_404(self, http):
        assert http.get("/download.html?room=nope&gmKey=nope").status_code == 404

    def test_download_with_a_wrong_key_is_a_404(self, http, make_session):
        make_session(room="dl-room")
        assert http.get("/download.html?room=dl-room&gmKey=wrong").status_code == 404

    def test_a_wrong_key_is_indistinguishable_from_a_missing_room(self, http, make_session):
        make_session(room="dl-room")
        wrong_key = http.get("/download.html?room=dl-room&gmKey=wrong")
        missing_room = http.get("/download.html?room=nope&gmKey=wrong")
        assert wrong_key.status_code == missing_room.status_code

    def test_image_for_an_unknown_room_is_a_404(self, http):
        assert http.get("/get_image.html?room=nope&id=abc").status_code == 404

    def test_image_with_an_unknown_id_is_a_404(self, http, make_session):
        make_session(room="img-room")
        assert http.get("/get_image.html?room=img-room&id=nope").status_code == 404
