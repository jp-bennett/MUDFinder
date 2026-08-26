# MUDFinder

A tool for running Pathfinder (and other d20) games over the internet, written
in Python 3 on flask-socketio. It is meant to feel like an old Multi-User
Dungeon, and to stand in for roll20 and D&D Beyond — though not all of that is
finished yet.

![The GM's view: a tavern battlemap with the party and a pirate ruffian on it,
the initiative order down the left, and the selected wizard's statblock in the
panel underneath](docs/screenshot.png)

## What it does

**The map.** Draw a grid or upload a battlemap image and align it to the
squares. Paint terrain, doors and stairs. Pick a token and click where it
should go; it can be turned a quarter at a time when the picture faces the
wrong way. Movement is pathfound and charged against the creature's speed, so a
move action stops where it should — around walls, through doors, and up a
staircase joining two levels drawn side by side on the same board.

**What the players can see.** Squares stay dark until somebody has line of
sight to them, and light levels are painted per square. The players' view is
built separately from the GM's rather than hidden with CSS, so an undiscovered
room is not in the page at all.

**The bestiary.** 10,332 creatures and 2,905 spells ship with it. Search by
name, CR or type, read the full statblock before choosing, and drop a group of
them into the encounter with their initiative rolled. A creature's attacks,
saves and limited-use spells are rolled from the panel under the map; any spell
name can be clicked for its rules.

**At the table.** Initiative order with HP tracking, chat, shared lore pages,
character sheets with inventory and spellbooks, and a read-only spectator link.
Who sees a roll follows who made it: a monster's save goes to the GM alone, a
player's goes to everyone.

## Running it

```
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python mudfinder.py
```

Then open <http://localhost:5000/> and create a game. You'll be sent to the GM
view, which has share links for players and spectators. Sessions are held in
memory and flushed to `saves/*.json` every five minutes and on shutdown.

Running `mudfinder.py` directly starts the Werkzeug development server, which is
fine for a game night on your own machine or LAN. To serve it publicly, run it
under a real server instead:

```
pip install gunicorn gevent gevent-websocket
gunicorn -k geventwebsocket.gunicorn.workers.GeventWebSocketWorker \
         -w 1 -b 0.0.0.0:5000 mudfinder:app
```

Use a **single worker**. Sessions live in the process, so a second worker would
serve a different set of games. If you put nginx in front, it has to pass the
websocket upgrade headers through, or Socket.IO will fail to connect while the
pages still load normally.

## Running the tests

```
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest
```

The suite covers the dice parser, the Unit/Player/Session save round trip, the
HTTP routes, and the Socket.IO event handlers. It needs no running server and no
network.

`tests/browser/` additionally drives a real Chromium against a real server
process, which is the only way to cover the browser Socket.IO client. Those need
a browser binary:

```
.venv/bin/playwright install chromium
```

Without one they skip, and the rest of the suite still runs. To select them:

```
.venv/bin/python -m pytest -m browser        # just the browser tests
.venv/bin/python -m pytest -m "not browser"  # everything else, ~3s
```

If Chromium is installed somewhere playwright does not expect, point
`MUDFINDER_CHROMIUM` at the binary.

## Notes for anyone working on it

`static/js/socket.io.js` is the vendored Socket.IO 4.x browser client. It has to
stay in the same generation as the server libraries, since the two negotiate an
Engine.IO protocol version between them. Read the comments in
`requirements.txt` before changing either, and run the browser tests afterwards
— a mismatch still serves every page normally and only fails at the websocket
handshake.

`shared.js` is loaded by all three views, and the spectator loads *only* that
one. Anything in it that calls into `gm.js` or `player.js` has to check the
function exists first, or the spectator gets a page that silently does nothing.

- [`docs/design.md`](docs/design.md) — the design language: the palette, the
  components built from it, and what was learned making each one.
- [`docs/security.md`](docs/security.md) — findings and the rules that came out
  of them.

## Licence

The MUDFinder project is licensed as AGPLv3 as a whole, but the individual
contributor contributions are licensed as GPLv3. The purpose of this is to allow
the project owner to add user management glue code in his offering of MUDFinder
as a service, and not distribute that glue code as part of this project.

Makes use of [DragSelect](https://github.com/ThibaultJanBeyer/DragSelect).
