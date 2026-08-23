# Known security findings

## Untrusted names are built into markup

**Status:** open. One instance fixed (the GM's player-links panel, `d41ad8e`);
the rest are listed below and still stand.

**Severity:** high. Confirmed to execute, in the GM's browser.

### The shape of it

Most of the app's lists are built by concatenating a string of HTML and
assigning it to `innerHTML`:

```js
document.getElementById("unitsDiv").innerHTML += `
  <div onclick="selectUnit(event, ${i})" class="unitListEntry">
    <div>  ${gmData.unitList[i].charName}</div>
  ...`;
```

Where the interpolated value is a loop counter or a unit number, that is fine —
a number cannot be anything but a number. Where it is a **name**, it is not,
because a name is whatever the person typed.

A player names itself in its own query string:

```
player.html?room=<room>&charName=Aria
```

`mudfinder.py` stores that name as it is given — see the `playerList` writes
around line 940, which do no validation — and hands it back to everyone in the
room on the next `gm_update`. So the name arrives in `drawUnits` and the list
builders as attacker-controlled text, and `innerHTML` reads it as markup.

Two different things go wrong depending on where the value lands:

| Where the name lands | What a hostile name does |
|---|---|
| Between tags, as element content | Closes the surrounding element and adds tags of its own — `<img src=x onerror=…>` runs on load |
| Inside a quoted handler, `onclick="fn('…')"` | A `'` closes the argument and the rest of the name becomes script in that handler |
| Inside an attribute, `id="…"` | Closes the attribute and adds attributes of its own |

### Confirmed

`static/js/gm.js:208` — `#unitsDiv`, interpolating `charName`.

Joining a room as

```
charName=Ari'a<img src=x onerror="window.pwned=1">
```

sets `window.pwned` in the GM's browser. This was found while testing the
links-panel fix and is reproducible: the name reaches the unit list, the `img`
is parsed as an element, its `src` 404s, and `onerror` runs.

That matters more than a defaced list. `gm.js` holds `room` and `gmKey` as
globals (set at line 93–94, from the GM's own URL). Script running on that page
can read both and hand them to anyone, which is control of the session — the
GM key is the only thing separating a GM from a spectator.

### Still to fix

| File | Line | Element | Untrusted value |
|---|---|---|---|
| `static/js/gm.js` | 208 | `#unitsDiv` | `charName` — **confirmed above** |
| `static/js/gm.js` | 216, 239 | `#initiativeDiv` | `charName` |
| `static/js/gm.js` | 269–270 | `#encountersDiv` | savegame name, three times over: as content, as `id="…"`, and inside `onclick="removeEncounter('…')"` |
| `static/js/gm.js` | 96–98 | `#linkDiv` | `room`, taken straight off `window.location.search` |
| `static/js/shared.js` | 995 | lore image | `loreURL`, straight into `src="…"` |
| `static/js/shared.js` | 999 | lore body | `loreText` |
| `static/js/shared.js` | 1006 | lore tab | `loreName`, as content and inside `onClick="…"` |

`player.js` and `spectator.js` were not swept — this list is what came out of
looking at `gm.js` and `shared.js`, and should not be read as complete.

### Why CodeQL is quiet about it

CodeQL reports alerts on **lines a pull request changes**. All of the above is
pre-existing, so it sits below the waterline and no PR is told about it. The
links panel was flagged on #21 only because that branch happened to rewrite
those four lines to add a wrapper — the sink itself was years old and no more
dangerous than its neighbours.

The corollary: a green CodeQL check is not evidence that these are gone. It
only means the current diff did not touch them.

### What the fix looks like

`d41ad8e` did the links panel, and is the pattern to copy:

- build with `createElement`, and put text in with `innerText`, never `innerHTML`
- wire handlers with `addEventListener` and a bound argument, not an `onclick`
  string — this is what removes the quote-breaking case entirely
- assemble URLs with `encodeURIComponent` per component

Numeric interpolations (`onclick="removeUnit(event, ${i})"`) are not the
problem and need not change, though they come out cleaner if the row is being
rebuilt anyway.

Escaping on the way out is the fix that holds. Validating names at the door is
worth doing as well, but it cannot be the only measure: saved games already on
disk may carry names from before the check existed, and those load straight
into the same lists.

### A note on the tests

`TestThePlayerLinksPanel` in `tests/browser/test_browser.py` checks the fixed
panel with a hostile name, and is deliberately scoped to `#links` rather than
asserting anything about the document. An assertion like `window.pwned is None`
would fail today — not because the panel is wrong, but because `#unitsDiv` on
the same page still runs the tag. Scoping it keeps the test about its own
subject; when the sinks above are fixed, a document-wide assertion becomes the
right one to add.
