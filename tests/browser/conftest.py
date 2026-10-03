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
import re
import shutil
import socket
import subprocess
import sys
import tempfile
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


def _read_log(log):
    log.flush()
    with open(log.name, "rb") as handle:
        return handle.read().decode("utf-8", "replace")


def _wait_until_serving(url, process, log, timeout=STARTUP_TIMEOUT):
    from urllib.error import URLError
    from urllib.request import urlopen

    deadline = time.time() + timeout
    while time.time() < deadline:
        if process.poll() is not None:
            raise RuntimeError(
                "server exited during startup with code %s:\n%s"
                % (process.returncode, _read_log(log))
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

    The server's output goes to a temporary file rather than a pipe. Nothing
    here reads that output until the server is asked for it, and the server
    logs a line per request; through a pipe, the suite eventually writes 64KB
    into a buffer no one is draining, at which point the server blocks on the
    write and stops answering. That looks like every test from that point on
    timing out on page.goto, with no clue as to why.
    """
    port = _free_port()
    log = tempfile.NamedTemporaryFile(prefix="mudfinder-server-", suffix=".log")
    process = subprocess.Popen(
        [
            sys.executable,
            "-c",
            "import mudfinder; mudfinder.socketio.run("
            "mudfinder.app, host='127.0.0.1', port=%d, "
            "allow_unsafe_werkzeug=True)" % port,
        ],
        cwd=REPO_ROOT,
        stdout=log,
        stderr=subprocess.STDOUT,
    )
    url = "http://127.0.0.1:%d" % port
    try:
        _wait_until_serving(url + "/", process, log)
        yield url
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
        log.close()


UNIT_FILE = os.path.join(REPO_ROOT, "deploy", "systemd", "mudfinder@.service")

# Set in the unit by EnvironmentFile; the test has to choose its own port
# anyway, so there is nothing gained by reproducing the env file too.
BIND_PLACEHOLDER = "${MUDFINDER_BIND}"


def _deployed_gunicorn_argv(port):
    """The deploy unit's ExecStart, as a list, pointed at a test port.

    Parsed out of the unit rather than restated, so that a unit edited to a
    worker class which cannot carry a websocket fails the tests that use it.
    systemd's continuation rules are the only parsing needed: a trailing
    backslash joins the next line, and the first token is the executable.

    That executable is an absolute path under /opt, which is not where
    gunicorn lives when running a test, so that one token is replaced.
    """
    with open(UNIT_FILE) as handle:
        body = handle.read()

    body = re.sub(r"\\\n\s*", " ", body)
    lines = [line for line in body.splitlines() if line.startswith("ExecStart=")]
    if len(lines) != 1:
        raise AssertionError(
            "expected exactly one ExecStart in %s, found %r" % (UNIT_FILE, lines)
        )

    argv = lines[0][len("ExecStart=") :].split()
    if BIND_PLACEHOLDER not in argv:
        raise AssertionError(
            "the unit no longer binds %s, so this fixture cannot give it a "
            "free port: %r" % (BIND_PLACEHOLDER, argv)
        )
    argv[argv.index(BIND_PLACEHOLDER)] = "127.0.0.1:%d" % port

    gunicorn = os.path.join(os.path.dirname(sys.executable), "gunicorn")
    if not os.path.exists(gunicorn):
        gunicorn = shutil.which("gunicorn")
    if gunicorn is None:
        pytest.skip(
            "gunicorn is not installed; it is in requirements-dev.txt. These "
            "tests run the deployed server rather than the development one."
        )
    argv[0] = gunicorn
    return argv


@pytest.fixture(scope="module")
def deployed_server(tmp_path_factory):
    """gunicorn, started exactly as deploy/ starts it; yields its base URL.

    Given its own working directory because SAVE_DIR is relative: run in the
    repository, this would drop test games into the developer's saves/. Only
    what the app reads is linked in.
    """
    port = _free_port()
    workdir = tmp_path_factory.mktemp("deployed")

    # Every top-level module and asset directory, rather than a list of the
    # ones the app happens to import today. A hand-written list silently drops
    # a new module, and a missing module here is not a failed import in the
    # report -- it is gunicorn's worker failing to boot, three screens of
    # traceback away from the name of the file that is not there.
    for name in sorted(os.listdir(REPO_ROOT)):
        if name.startswith(".") or name in ("saves", "tests", "deploy", "docs"):
            continue
        if name.endswith(".py") or name in ("static", "templates", "tools") \
                or name.endswith(".sql"):
            os.symlink(os.path.join(REPO_ROOT, name), str(workdir / name))
    (workdir / "saves").mkdir()

    argv = _deployed_gunicorn_argv(port)
    log = open(str(workdir / "server.log"), "w+b")
    process = subprocess.Popen(
        argv, cwd=str(workdir), stdout=log, stderr=subprocess.STDOUT
    )
    url = "http://127.0.0.1:%d" % port
    try:
        _wait_until_serving(url + "/", process, log)
        yield url
    finally:
        # The same shutdown the unit relies on to flush saves/: SIGTERM to the
        # master, which stops its own worker. TimeoutStopSec in the unit is 60.
        process.terminate()
        try:
            process.wait(timeout=30)
        except subprocess.TimeoutExpired:
            process.kill()
        log.close()


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
