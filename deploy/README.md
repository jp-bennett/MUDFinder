# Deploying MUDFinder

Two instances on one host, each keeping itself up to date:

| instance | follows | deploys when |
|---|---|---|
| beta | `master` | anything lands on master |
| primary | GitHub Releases | a release is published |

updatecli resolves the version and writes it to a file. A systemd path unit
notices the file changed and runs the deploy. Nothing else.

**That split is deliberate.** updatecli runs `shell` targets even under
`updatecli diff`, so a manifest that deployed directly would restart a live
game server while you were asking it what it would do. The manifests here only
ever write a file, which makes `diff` safe to run at any time — and that was
checked rather than assumed:

```
$ updatecli diff --config deploy/updatecli/beta.yaml
  * Changed: 1
$ cat /opt/mudfinder-beta/DEPLOY_TARGET     # untouched
0000000000000000000000000000000000000000
```

## Layout

```
/opt/mudfinder-beta/      checkout, venv, saves/, DEPLOY_TARGET
/opt/mudfinder-primary/   the same, for the release instance
/opt/mudfinder-deploy/    this directory, checked out on its own
/etc/mudfinder/           beta.env, primary.env, updatecli.env
/usr/local/bin/mudfinder-deploy
```

Instances are named `beta` and `primary`, and the systemd units are templates
on those names — `mudfinder@beta.service`, `mudfinder-deploy@primary.path` and
so on. The directory names follow, which is why the release instance is at
`/opt/mudfinder-primary` rather than `/opt/mudfinder`.

## Installing

```sh
useradd --system --home-dir /opt/mudfinder-beta mudfinder

for i in beta primary; do
    git clone https://github.com/jp-bennett/MUDFinder.git /opt/mudfinder-$i
    python3.11 -m venv /opt/mudfinder-$i/.venv
    /opt/mudfinder-$i/.venv/bin/pip install -r /opt/mudfinder-$i/requirements.txt
    /opt/mudfinder-$i/.venv/bin/pip install gunicorn gevent packaging
    chown -R mudfinder: /opt/mudfinder-$i
done

git clone https://github.com/jp-bennett/MUDFinder.git /opt/mudfinder-deploy
install -m 755 /opt/mudfinder-deploy/deploy/mudfinder-deploy /usr/local/bin/

mkdir -p /etc/mudfinder
cp /opt/mudfinder-deploy/deploy/systemd/*.env.example /etc/mudfinder/
# rename each to <instance>.env and updatecli.env, fill in the token
chmod 600 /etc/mudfinder/updatecli.env

cp /opt/mudfinder-deploy/deploy/systemd/mudfinder*.{service,path,timer} \
   /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now mudfinder@beta mudfinder@primary
systemctl enable --now mudfinder-deploy@beta.path mudfinder-deploy@primary.path
systemctl enable --now mudfinder-updatecli@beta.timer
systemctl enable --now mudfinder-updatecli@primary.timer
```

**One instance at a time is fine, and is how this was first installed.** Do
only the `beta` half of all of that and the server runs beta alone; add
primary later by repeating it with the other name. Nothing is shared but
`/opt/mudfinder-deploy` and the units themselves.

Do not, though, enable `mudfinder-updatecli@primary.timer` before
`/opt/mudfinder-primary` is a clone. The manifest's file target creates the
directory it writes into, so it would leave a root-owned `/opt/mudfinder-primary`
holding nothing but `DEPLOY_TARGET` -- and `git clone` refuses a directory that
is not empty, so the real install then fails for a reason that looks unrelated.

`beta` needs no GitHub token: its manifest asks `git ls-remote` for the head of
master, which wants no credentials. Only `primary` reads
`/etc/mudfinder/updatecli.env`, and the unit treats that file as optional, so a
beta-only server can skip it.

`packaging` is in that pip line because gunicorn's gevent worker imports it
without declaring it. Without it the unit starts, fails to load the worker
class, and systemd restarts it on a loop -- the journal shows a
`ModuleNotFoundError` inside gunicorn's own import machinery, which does not
look like a missing dependency of yours.

If nginx answers 502 while `curl` on the host returns 200, the instance is
bound somewhere the proxy cannot route to -- see MUDFINDER_BIND in
beta.env.example. A proxy on another machine cannot reach 127.0.0.1 here.

If every page loads but no game ever appears, and the browser console says
`Invalid frame header` on the `socket.io/?...&transport=websocket` request,
the unit is running the wrong gunicorn worker. It must be `-k gevent`.
`gevent-websocket`'s `GeventWebSocketWorker` is the one that looks right and
breaks this: the app runs in `async_mode="threading"`, so Engine.IO opens the
websocket itself and handshakes a connection that worker has already
handshaked. Nothing in the journal says so, and nginx is not involved -- the
same failure reproduces with no proxy at all.

nginx goes in front of the two ports — see "Behind a reverse proxy" and
"Serving it under a subpath" in the top-level README.

## Two things that will bite

**`WorkingDirectory` is not decoration.** `SAVE_DIR` is the relative string
`"saves"`, resolved against the process's working directory. Point the unit
somewhere else and the instance writes its games somewhere else and reads none
of the ones it had.

**Never add `git clean -x` to the deploy script.** `saves/` and `.venv*/` are
gitignored and untracked, so `git reset --hard` leaves both alone. `-x` would
delete every saved game on the host.

## What a restart costs

Sessions live in the gunicorn process, so a deploy disconnects whoever is
playing. The games themselves survive: the rooms are written to `saves/` by an
`atexit` handler and read back on the next request for the room.

That handler does not run on a bare SIGTERM — `atexit` runs because gunicorn
catches the signal and exits the worker cleanly. Measured on an idle instance,
that takes about two seconds:

```
$ kill -TERM <gunicorn master>
Attempting cleanup
Bye
$ ls saves/
sigtermprobe.json
```

Which is why `mudfinder@.service` sets `KillMode=mixed` and
`TimeoutStopSec=60`, above gunicorn's `--graceful-timeout 30`. If systemd ever
loses patience first and sends SIGKILL, the handler does not run and you lose
up to five minutes of play — the autosave interval.

The primary deploys as soon as a release appears, by choice. If that turns out
to be wrong in practice, the place to change it is the deploy script: have it
exit 0 without restarting when the instance has connected clients, and let the
next timer tick pick it up.

## The GitHub token

`deploy/updatecli/primary.yaml` uses the `githubrelease` source, which needs a
token even though the repository is public, and talks to GitHub's **GraphQL**
API. A fine-grained token with no permissions at all is enough. If the host
firewall allows the REST API but not GraphQL, this is where it will fail, and
the fix is to switch that manifest to the `gittag` source — which needs
neither, at the cost of firing on any `v*` tag rather than only on a published
release.

## Checking it

```sh
updatecli diff --config /opt/mudfinder-deploy/deploy/updatecli/beta.yaml
systemctl start mudfinder-deploy@beta      # force one by hand
journalctl -u mudfinder-deploy@beta -n 50
systemctl list-timers 'mudfinder-updatecli@*'
journalctl -u mudfinder-updatecli@beta -n 20
```

The deploy script is safe to run at any time: it does nothing when the checkout
is already at the recorded ref, refuses an empty `DEPLOY_TARGET`, and exits
quietly when there is no `DEPLOY_TARGET` at all.

Until the first release is cut, the primary manifest resolves nothing and
writes nothing. That is the correct behaviour before there is a release, not a
misconfiguration.
