# Known security findings

## Untrusted names are built into markup

**Status:** closed. Sixteen sinks across four files, found by a full sweep and
fixed together. `TestAHostileNameRunsNowhere` is the regression test; it failed
on every view before the change.

**Severity, while it stood:** high. A player could run script in the GM's
browser, and in every other player's, by naming itself.

### The shape of it

Most of the app's lists were built by concatenating a string of HTML and
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

`mudfinder.py` stores that name as it is given — the `playerList` writes around
line 940 do no validation — and hands it back to everyone in the room on the
next `gm_update`. So the name arrived in the list builders as attacker-controlled
text, and `innerHTML` read it as markup.

Three things went wrong depending on where the value landed:

| Where it landed | What a hostile name did |
|---|---|
| Between tags, as element content | Closed the surrounding element and added tags of its own — `<img src=x onerror=…>` runs on load |
| Inside a quoted handler, `onclick="fn('…')"` | A `'` closed the argument and the rest of the name became script in that handler |
| Inside an attribute, `id="…"` or `value="…"` | Closed the attribute and added attributes of its own |

### What was fixed

Sixteen sinks. The first was found on #21 because that branch happened to touch
those lines; the rest came out of sweeping every `innerHTML` in the client for
one that interpolates something a person typed.

| File | Element | Untrusted value |
|---|---|---|
| `gm.js` | `#linkDiv` | `room`, off the query string |
| `gm.js` | `#unitsDiv` | `charName` |
| `gm.js` | `#initiativeDiv` | `charName` |
| `gm.js` | `#encountersDiv` | savegame name — as content, as `id=`, and inside `onclick` |
| `shared.js` | lore page | `loreURL` into `src=`, and `loreText` |
| `shared.js` | lore tabs | `loreName`, as content and inside `onClick` |
| `player.js` | `#initiativeDiv` | `charName` |
| `player.js` | `#unitsDiv` | `charName` |
| `player.js` | `#promptDiv` | `charName` |
| `player.js` | `#inventoryTitle` | bag name, inside `onclick` |
| `player.js` | item rows | `itemWeight`, `itemValue`, `itemCount` into `value=` |
| `player.js` | `#inventoryTabs` | bag name, as content and inside `onClick` |
| `player.js` | `#selectCaster` | caster class |
| `player.js` | spell picker | caster class, inside a quoted `onchange` argument |
| `spectator.html` | `#initiativeDiv` | `charName` |
| `spectator.html` | `#connectedPlayers` | `charName` |

### The rules that came out of it

- **Build with `createElement`, and put text in with `innerText`.** Never
  `innerHTML` with anything interpolated into it.
- **Wire handlers with `addEventListener` and a bound argument**, never an
  `onclick` string. This is what removes the quote-breaking case outright rather
  than trying to escape it.
- **Set attributes as properties** — `img.src = …`, `input.value = …` — so a
  quote cannot add attributes beside them.
- **Assemble URLs with `encodeURIComponent`** per component.
- **Never use a typed name as an element id.** An id cannot hold a space or a
  quote. The saved encounters keep theirs in `dataset.encounter` instead.
- **`innerHTML +=` destroys bound handlers.** It reads the element back, adds to
  the text and reparses the lot, so anything already appended comes back as a
  fresh element with none of its listeners. Anywhere a list is built with
  `appendChild`, everything added after it has to be as well. The lore page's
  Add form was exactly this trap.

Numeric interpolations (`onclick="removeUnit(event, ${i})"`) were never the
problem, and the ones that remain are left alone.

### What is deliberately still markup

`spellTextObj.innerHTML = spellText` in `shared.js` is the bundled spells
table's own `description_formated`, which ships as HTML with its italics and
paragraphs in it. That is our asset rather than anything anybody typed. It is
annotated as deliberate at the call site.

`table.innerHTML = gpTableSavedHTML` and its inventory twin restore markup
saved off the page's own template at load. Same reasoning.

### The one thing left, and why it is left

The player's own spellbook and prepared-spell tables are still built as markup,
and interpolate the spell rows held in that player's `spellcasting`. In normal
use those rows come out of the bundled spells table. A player who tampered with
their own client could put markup in one.

That renders on **the owning player's page and nowhere else** — the GM's
creature panel reads `unit.castings`, which is a different field parsed from the
bestiary — so the worst available is self-XSS, which is not a vulnerability in
the usual sense: anyone can already run script in their own browser. Converting
those two tables is worth doing when they are next touched for another reason,
but it is not a hole.

### Why CodeQL was quiet about all of it

CodeQL reports alerts on **lines a pull request changes**. All of this was
pre-existing, so it sat below the waterline and no PR was told. The links panel
was flagged on #21 only because that branch happened to rewrite those four lines
to add a wrapper — the sink itself was years old and no more dangerous than its
neighbours.

The corollary, which still holds for whatever is next: a green CodeQL check is
not evidence that a file is clean. It only means the current diff did not touch
the parts that are not.
