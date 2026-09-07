"""Tests for the plain HTTP routes."""

import base64
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


PNG = b"\x89PNG\r\n\x1a\n" + b"body"
JPEG = b"\xff\xd8\xff\xe0" + b"body"
GIF = b"GIF89a" + b"body"
WEBP = b"RIFF" + b"\x00\x00\x00\x00" + b"WEBP" + b"body"
SVG = b"<svg xmlns='http://www.w3.org/2000/svg'></svg>"


def planted(make_session, room, raw, image_id="abc"):
    session = make_session(room=room)
    session.images[image_id] = base64.b64encode(raw).decode()
    return session


class TestGetImage:
    def test_image_is_returned(self, http, make_session):
        session = make_session(room="img-room")
        # base64 for the bytes b"hello"
        session.images["abc"] = "aGVsbG8="
        response = http.get("/get_image.html?room=img-room&id=abc")
        assert response.status_code == 200
        assert response.data == b"hello"

    def test_the_same_image_at_the_path_url(self, http, make_session):
        """The shape store_image hands out now. Relative from the page, so it
        follows the app under a subpath the way every other link does."""
        planted(make_session, "img-room", PNG)
        response = http.get("/images/img-room/abc")
        assert response.status_code == 200
        assert response.data == PNG

    def test_the_old_url_still_serves(self, http, make_session):
        """Saves, running rooms and saved encounters are full of these."""
        planted(make_session, "img-room", PNG)
        response = http.get("/get_image.html?room=img-room&id=abc")
        assert response.status_code == 200
        assert response.data == PNG


class TestAnImageCanBeCached:
    """Every redraw refetched every token: the client rebuilds img.src on each
    update, and the response carried no Cache-Control, no ETag and no
    Last-Modified, so a browser had nothing to reuse."""

    def test_it_may_be_kept(self, http, make_session):
        planted(make_session, "cache-room", PNG)
        response = http.get("/images/cache-room/abc")
        assert "max-age=" in response.headers["Cache-Control"]
        assert "public" in response.headers["Cache-Control"]

    def test_it_carries_a_validator(self, http, make_session):
        planted(make_session, "cache-room", PNG)
        assert http.get("/images/cache-room/abc").headers.get("ETag")

    def test_the_old_url_is_cacheable_too(self, http, make_session):
        planted(make_session, "cache-room", PNG)
        response = http.get("/get_image.html?room=cache-room&id=abc")
        assert "max-age=" in response.headers["Cache-Control"]

    def test_a_second_ask_is_answered_not_modified(self, http, make_session):
        """What the caching is for: the bytes go out once."""
        planted(make_session, "cache-room", PNG)
        etag = http.get("/images/cache-room/abc").headers["ETag"]
        again = http.get("/images/cache-room/abc",
                         headers={"If-None-Match": etag})
        assert again.status_code == 304
        assert again.data == b""


class TestAnImageSaysWhatItIs:
    """The route answered "image", which is not a media type. Nothing records a
    type at upload -- the client's data URI prefix carries no subtype -- so it
    is read off the front of the file, which also covers images already stored
    in live rooms."""

    def test_a_png(self, http, make_session):
        planted(make_session, "type-room", PNG)
        assert http.get("/images/type-room/abc").mimetype == "image/png"

    def test_a_jpeg(self, http, make_session):
        planted(make_session, "type-room", JPEG)
        assert http.get("/images/type-room/abc").mimetype == "image/jpeg"

    def test_a_gif(self, http, make_session):
        planted(make_session, "type-room", GIF)
        assert http.get("/images/type-room/abc").mimetype == "image/gif"

    def test_a_webp(self, http, make_session):
        planted(make_session, "type-room", WEBP)
        assert http.get("/images/type-room/abc").mimetype == "image/webp"

    def test_an_svg(self, http, make_session):
        planted(make_session, "type-room", SVG)
        assert http.get("/images/type-room/abc").mimetype \
            == "image/svg+xml"

    def test_something_unrecognisable_is_not_called_an_image(self, http, make_session):
        planted(make_session, "type-room", b"not a picture at all")
        assert http.get("/images/type-room/abc").mimetype \
            == "application/octet-stream"

    def test_the_old_url_says_it_too(self, http, make_session):
        planted(make_session, "type-room", PNG)
        response = http.get("/get_image.html?room=type-room&id=abc")
        assert response.mimetype == "image/png"


class TestAMissingImageAtThePathUrl:
    def test_an_unknown_room_is_a_404(self, http):
        assert http.get("/images/nope/abc").status_code == 404

    def test_an_unknown_id_is_a_404(self, http, make_session):
        make_session(room="img-room")
        assert http.get("/images/img-room/nope").status_code == 404


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


class TestTheBasePath:
    """Where the instance is served from, for the Socket.IO client's benefit.

    Everything else on these pages is linked relatively and follows the page
    wherever it is served. The Socket.IO client is the exception: it builds its
    own URL from the origin and a path, absolute from the root, so behind a
    proxy at /beta it asks for /socket.io/ while the app is at /beta/socket.io/
    and simply never connects.
    """

    def test_nothing_set_means_the_root(self):
        assert mudfinder.normalise_base_path(None) == ""
        assert mudfinder.normalise_base_path("") == ""
        assert mudfinder.normalise_base_path("/") == ""

    def test_a_leading_slash_is_added_if_it_is_missing(self):
        assert mudfinder.normalise_base_path("beta") == "/beta"

    def test_a_trailing_slash_is_dropped(self):
        """So the path is joined to "/socket.io" without doubling the slash."""
        assert mudfinder.normalise_base_path("/beta/") == "/beta"

    def test_whitespace_and_quotes_from_a_shell_are_dropped(self):
        assert mudfinder.normalise_base_path('  "/beta/"  ') == "/beta"

    def test_a_deeper_path_survives(self):
        assert mudfinder.normalise_base_path("/games/beta/") == "/games/beta"

    def test_every_page_is_told_where_it_is(self, http):
        """All four connect a socket, so all four need it."""
        for page in ("/", "/gm.html", "/player.html", "/spectator.html"):
            body = http.get(page).get_data(as_text=True)
            assert 'var SOCKETIO_PATH = "%s"' % mudfinder.SOCKETIO_PATH in body, page

    def test_the_default_is_what_it_always_was(self, http):
        """An instance at the root is configured with nothing at all, and asks
        for the same URL it asked for before any of this existed."""
        assert mudfinder.SOCKETIO_PATH == "/socket.io"
        body = http.get("/").get_data(as_text=True)
        assert 'var SOCKETIO_PATH = "/socket.io"' in body

    def test_the_client_is_given_the_path_whole(self):
        """Not a prefix it appends "/socket.io" to itself -- that produced
        /beta/socket.io/socket.io, which reaches nothing."""
        body = open("templates/index.html", encoding="utf-8").read()
        assert "SOCKETIO_PATH) + \"/socket.io\"" not in body
        assert 'path: (typeof SOCKETIO_PATH === "undefined" ? "/socket.io" : SOCKETIO_PATH)' in body


class TestTheLandingPageSurvivesNoConnection:
    def test_the_gm_key_does_not_wait_for_the_socket(self):
        """It is a random string and owes the connection nothing. Assigned in
        the connect handler, a websocket that never arrived left it undeclared,
        so Create Game threw "gmKey is not defined" from a button -- three
        steps from the connection that was the actual problem."""
        body = open("templates/index.html", encoding="utf-8").read()
        assert "var gmKey = Math.random()" in body

    def test_a_failed_connection_says_so(self):
        """There is no polling fallback -- upgrade is off -- so a proxy that
        does not pass the handshake fails outright, and used to do it in
        silence while every page still rendered."""
        body = open("templates/index.html", encoding="utf-8").read()
        assert "connect_error" in body
        assert "connectionState" in body

    def test_the_message_has_its_own_element(self):
        """Not the card: the card holds the form, and writing the message into
        it took the form with it."""
        body = open("templates/index.html", encoding="utf-8").read()
        assert '<div id="connectionState"' in body
        assert 'document.getElementById("connectionState").innerText' in body
