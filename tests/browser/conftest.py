"""Fixtures for the end-to-end browser tests.

These drive a real Chromium against a real server process, which is the only
way to cover the browser Socket.IO client. The unit-level Socket.IO tests in
tests/test_socketio.py talk to the handlers directly and so cannot see a
handshake failure between the vendored client and the server libraries -- that
failure is invisible until a browser tries to connect.

playwright is imported lazily inside the fixtures so that collecting the rest
of the suite does not require it.
"""

import os
import socket
import subprocess
import sys
import time

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STARTUP_TIMEOUT = 60.0

# Set this when the local Chromium is not where playwright expects it, e.g.
#   MUDFINDER_CHROMIUM=/opt/pw-browsers/chromium pytest -m browser
CHROMIUM_ENV_VAR = "MUDFINDER_CHROMIUM"


def _free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _wait_until_serving(url, process, timeout=STARTUP_TIMEOUT):
    from urllib.error import URLError
    from urllib.request import urlopen

    deadline = time.time() + timeout
    while time.time() < deadline:
        if process.poll() is not None:
            raise RuntimeError(
                "server exited during startup with code %s:\n%s"
                % (process.returncode, process.stdout.read().decode("utf-8", "replace"))
            )
        try:
            with urlopen(url, timeout=1) as response:
                if response.status == 200:
                    return
        except (URLError, OSError):
            time.sleep(0.2)
    raise RuntimeError("server did not start within %.0f seconds" % timeout)


@pytest.fixture(scope="session")
def live_server():
    """Run mudfinder in a subprocess on a free port; yield its base URL.

    The port is chosen at run time rather than using the hardcoded 5000 from
    __main__, so the tests do not collide with a development server.
    """
    port = _free_port()
    process = subprocess.Popen(
        [
            sys.executable,
            "-c",
            "import mudfinder; mudfinder.socketio.run("
            "mudfinder.app, host='127.0.0.1', port=%d, "
            "allow_unsafe_werkzeug=True)" % port,
        ],
        cwd=REPO_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    url = "http://127.0.0.1:%d" % port
    try:
        _wait_until_serving(url + "/", process)
        yield url
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()


@pytest.fixture(scope="session")
def browser():
    playwright_module = pytest.importorskip("playwright.sync_api")

    launch_kwargs = {}
    executable = os.environ.get(CHROMIUM_ENV_VAR)
    if executable:
        launch_kwargs["executable_path"] = executable

    with playwright_module.sync_playwright() as playwright:
        try:
            instance = playwright.chromium.launch(**launch_kwargs)
        except Exception as exc:  # no browser binary available
            pytest.skip(
                "could not launch Chromium (%s). Run 'playwright install chromium', "
                "or point %s at an existing binary."
                % (str(exc).split("\n")[0], CHROMIUM_ENV_VAR)
            )
        yield instance
        instance.close()


class Client:
    """A page plus the console errors, JS exceptions, and failed requests it produced."""

    def __init__(self, page):
        self.page = page
        self.console_errors = []
        self.page_errors = []
        self.failed_requests = []
        page.on(
            "console",
            lambda message: (
                self.console_errors.append(message.text)
                if message.type == "error"
                else None
            ),
        )
        page.on("pageerror", lambda error: self.page_errors.append(str(error)))
        page.on(
            "requestfailed",
            lambda request: self.failed_requests.append(request.url),
        )

    @property
    def errors(self):
        return self.console_errors + self.page_errors

    def local_request_failures(self, base_url):
        """Failed requests to the app itself, ignoring third-party hosts.

        templates/player.html pulls a stylesheet from fontlibrary.org, so an
        offline or network-restricted machine always has one external failure
        that says nothing about the app.
        """
        return [url for url in self.failed_requests if url.startswith(base_url)]

    def external_request_failures(self, base_url):
        """Failed requests to hosts other than the app."""
        return [url for url in self.failed_requests if not url.startswith(base_url)]

    def socket_connected(self):
        """Whether the page's Socket.IO client reports an open connection."""
        return self.page.evaluate(
            "() => typeof socket !== 'undefined' && socket !== null && socket.connected === true"
        )


@pytest.fixture
def new_client(browser):
    """Factory for browser pages; every page created is closed at teardown."""
    contexts = []

    def _new(url=None):
        context = browser.new_context(viewport={"width": 1400, "height": 900})
        contexts.append(context)
        client = Client(context.new_page())
        if url:
            client.page.goto(url)
        return client

    yield _new
    for context in contexts:
        context.close()


@pytest.fixture
def gm_client(live_server, new_client):
    """A browser sitting in the GM view of a freshly created game.

    Returns (client, room, gm_key).
    """
    client = new_client(live_server + "/")
    client.page.wait_for_function("() => typeof socket !== 'undefined' && socket.connected")
    client.page.fill("#gameName", "Browser Test Game")
    client.page.click("text=Create Game")
    client.page.wait_for_url("**/gm.html*", timeout=15000)
    client.page.wait_for_selector("#mapForm", state="attached")

    query = client.page.url.split("?", 1)[1]
    params = dict(pair.split("=", 1) for pair in query.split("&"))
    return client, params["room"], params["gmKey"]
