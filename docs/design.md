# MUDFinder design language

The monster statblock worked out a look for itself: ink on the parchment the
maps are already drawn on, ruled in a dry tan, with section headings in small
caps under a double rule. It read like a page out of a bestiary, which is
exactly what it is.

The rest of the app was still browser default — black hairlines on `lightgray`,
raw `<button>` bevels, captions floating above bordered boxes. This document is
the statblock's palette generalised so everything else can be built from it.

The reference is the **Long Room at Trinity College Dublin**: dark polished
mahogany, a warm pool of light down the middle falling away to shadow at the
edges, gilt lettering on the gallery rail, and cream vellum and marble standing
out bright against all of it.

Its grain came from a closer reference: a photograph of a walnut cabinet
against dark woven cloth. Real furniture grain is **fine and dense** — many
close fibres with a few stronger figure lines through them, not a handful of
lazy wide ones — and the warm timber is nearly always set against a cool dark
weave.

So the app is made of **three materials**:

| | |
|---|---|
| **Timber** | The desk everything sits on. Warm walnut, lit from above. |
| **Cloth** | A dark navy weave. The tab bar and the statblock name plates — wherever light lettering sits on a dark ground. |
| **Paper** | Panels, forms, the statblock. Pages laid on the desk, each casting a small shadow. |

Ink is what is written on the paper; gilt is what is lettered on the cloth.
Everything below follows from that.

## Tokens

Every colour, radius and rule in `static/css/mudfinder.css` comes from `:root`.
**Nothing below the token block should name a colour of its own.** If a
component needs a shade that is not here, the right move is to add a token, not
a hex code.

### Ink

| Token | Value | For |
|---|---|---|
| `--ink` | `#211711` | Body text, the tab bar, statblock header bars |
| `--ink-soft` | `#4d3f2f` | Headings — present without shouting |
| `--ink-faint` | `#857a66` | Field names, hints, the rule under a section heading |

Three weights, no more: the text itself, something said quietly beside it, and
a label that exists only to name the thing under it.

### Paper

| Token | Value | For |
|---|---|---|
| `--paper` | `#f5efdf` | Panel and form surfaces; text on an ink ground |
| `--paper-warm` | `#e7dbc2` | Panel headings, alternating table rows, a pressed button |
| `--desk` | `#3f2a1c` | The walnut behind everything |
| `--cloth` | `#232a33` | The woven ground under the tab bar and the statblock plates |
| `--desk-light` | two gradients | The pool of light, and the fall-off to the edges |

### Rules

| Token | Value | For |
|---|---|---|
| `--rule` | `#b09763` | Every border in the chrome |
| `--rule-faint` | `rgba(201,162,89,0.45)` | Borders on an ink ground, dividers inside a panel |
| `--gilt` | `#c9a227` | Lettering **on dark grounds only** — the tab bar, the session links |

Borders are **ruled lines, not hairlines**. The tan reads as part of the paper;
black reads as a box drawn on top of it. This single substitution is most of
what makes the app look designed rather than assembled.

### Accent and alarm

| Token | Value | For |
|---|---|---|
| `--accent` | `#3f6f57` | What is selected, what has focus |
| `--accent-soft` | `#dde8df` | What the pointer is over |
| `--danger` | `#8f2f22` | Destruction, and the unit whose turn it is |

The accent is the green of the ropes strung between the busts. It replaced
cornflower blue, which was the one colour in the app that had nothing to do
with a library.

One accent. It means *chosen*. Using it for decoration costs it that meaning.

### Shape and grain

| Token | Value | For |
|---|---|---|
| `--radius` | `3px` | Controls: buttons, inputs, cells |
| `--radius-panel` | `6px` | The sheets those controls sit on |
| `--palette-height` | `94px` | The tool palette under the map, and what the map leaves it |
| `--heading-tracking` | `0.09em` | Letter-spacing on small-caps headings |
| `--shadow-resting` | soft, close | A page lying on the desk: panels and form cards |
| `--shadow-lifted` | deep, wide | Something floating above it: only the monster picker |
| `--desk-grain` | inline SVG | The timber |
| `--cloth-weave` | inline SVG | The weave |

Wood is two things at once, so the desk is two layers.

**The board** is turbulence read directly as colour: a very anisotropic
`fractalNoise` — frequent across the grain, barely varying along it — mapped
through a colour table into walnut, then waved by a slow displacement so it is
not sawn dead straight.

Gradient stripes cannot do this. Displacing them slides bands sideways but
cannot make one wider than its neighbour or fade one out, which is most of what
grain actually does — three attempts went that way and all three read as
corduroy.

**The growth rings** are separate, and they are what those attempts kept
missing: they are hard-edged incised lines, not blur. A **`discrete`** transfer
function turns the noise into hard on/off bands, and taking one narrow band in
seven gives fine continuous rings that crowd together and open out the way real
ones do.

**The desk is planked.** Each board is cut from a different part of the tree and
carries its own tone — that is the cue that actually reads, because a seam line
on its own gets lost among the growth rings, which are dark vertical lines too.
The seams are grooves rather than pen lines (shadow in the gap, the lit edge of
the next board beside it) and they are spaced **irregularly**, since even
spacing reads as tiling.

**The boards have knots**: a dark core, the ring of harder wood around it, and
two rings of grain crowding past. They sit inside boards rather than across a
join, and they are **unevenly distributed** — some boards are clear, some are
full of them. Three per board is a grid, which is what the first placement
looked like. All six of those rules have tests.

**The rustic cues are kept quiet.** Knots, contrast between boards and the depth
of the seams are exactly what makes timber read as *barn floor* rather than as
*joinery*, so all three are drawn at well under half strength, and the light is
low. The room this is meant to be is a study after dark. A bright pool of light
in the middle of it undoes the whole effect on its own.

There is deliberately **no broad light-and-dark pass in the timber**. The desk
gets that from `--desk-light`, and an earlier version that did it in both places
flattened the colour instead of deepening it. There is a test that the grain
holds exactly three turbulences.

Two rules the tests enforce, both learned the hard way:

- **The board and the rings must be at least 10× more frequent across the grain
  than along it.** Even in both axes they are blobs.
- **The rings must be one octave.** Further octaves vary the noise *along* the
  ring as well as across it, and the discrete step turns that variation into a
  dashed line rather than a continuous one.

The wave, by contrast, must stay below `0.01` in both axes: it plays out over
hundreds of pixels, and in the tens it reads as fur.

The cloth is the same family of technique at a different scale — a 6px
over-under weave displaced by a *small* turbulence, just enough that the threads
are not machine-perfect, with a noise pass overlaid as fibre.

It is woven **faintly**, at well under half the contrast the timber's grain
gets. The tab bar is a strip forty pixels tall carrying eight labels, and a
weave you can actually see in it competes with them. The threads are there to
stop the bar reading as flat paint, not to be looked at.

Both are drawn rather than downloaded because **the app fetches nothing** from
anywhere: the player page used to pull a font from fontlibrary.org on every
load, which made it depend on a third party and fail when offline. A test walks
every template, stylesheet and script and fails on any `src`/`href`/`url()`
naming an external host — it found two live ones on first run, pointing at the
author's own server.

The desk is painted once, on `body`, at `background-size: cover` with
`background-attachment: fixed`: one piece of wood across the window rather than
a tile with seams. `#mapContainer` is **transparent** so that piece shows
through, rather than laying a second one over it out of register.

## Type

One face throughout: Liberation Serif, falling back to the metric-compatible
Times New Roman, then whatever serif the browser has. A virtual tabletop for a
game played out of hardback books should be set in a serif.

**Headings are small caps with letter-spacing, under a rule.** This is the one
piece of the statblock that carries the most identity, and it costs nothing to
apply everywhere:

- `.sbHeading` — inside a statblock. Double rule in `--rule`.
- `.panelHeading` — the bar across the top of a panel. `--paper-warm` ground,
  single rule under.
- `.sectionHeading` — names a form or a region with no card edge to sit against.
  Double rule in `--ink-faint`.
- `.fieldLabel` / `.fieldLabelInline` — names one field, in `--ink-faint`.

Field names carry **no trailing colon**. The small caps and the colour already
say it is a label.

## Components

`.bottomDiv` — the player's action bar — is a panel too: same sheet, same ruled
heading, with a `.bottomDivBody` under it that scrolls while the heading stays.
It takes a quarter of the height rather than a fifth, because the heading costs
a line and its five action buttons are stacked.

### Panel — `.panel` + `.panelHeading`

A sheet on the desk with its name ruled across the top. The initiative order,
the creature list, the chat and the connected players are all one of these, so
they read as the same kind of thing instead of three differently-bordered boxes
with a floating caption above each.

The heading belongs **inside** the panel. A caption sitting above a border is
the thing this replaces.

### Tab sheet — `.tabSheet`

A tab panel holding **one continuous document** rather than a set of cards: the
character sheet, the inventory, the lore pages, the player links. Paper, ruled,
with the resting shadow, filling its holder.

`.mapSheet` is the modifier for the map tab: the same box, but with no padding
and no scroll of its own, since everything inside it — the map, the palette, the
alignment bar — is absolutely positioned. It has to be `position: relative` or
those three measure themselves against the tab holder and reach past the sheet.

The distinction from `.formCard` is what the panel *is*. Distinct groupings that
happen to share a tab are cards standing on the desk; one thing that would be
printed on a single page is a sheet.

Two rules it has to obey, both learned by breaking them:

- **An id beats a class.** A leftover `height: 100%` on `#lore` overrode the
  sheet's own `calc(100% - 16px)` and drew the box over the scrollbar.
- **Clamp to the window, not only to the holder.** The player view's
  `#activeTabDiv` is forty pixels taller than the window it sits in — on master
  too — so a sheet sized to the holder alone puts its foot below the fold.
  `max-height: calc(100vh - 56px)`.

Tab strips **inside** a sheet — the lore pages, the inventory list — are on
paper, so `.tabSheet .tab` overrides the gilt-on-dark treatment the main bar
uses. Scoping it to `.tabSheet` rather than naming the two strips means any
future one is covered.

### Form card — `.formCard`

The same sheet, sized to its contents rather than to a column: the encounter
builder, the unit sheet, the house rules, the landing page. `display:
inline-block`, so two of them sit side by side if there is room.

### Buttons

Paper with a ruled edge and a `--radius` corner — a key, not a bevel. Hover
tints to `--accent-soft`; focus draws a `--accent` outline.

Buttons **on a list row** (`.InitEntry`, `.unitListEntry`, `.encountersDiv`)
keep tighter metrics. The left column is a fifth of the window and an initiative
entry carries several of them; the roomier padding pushed the last one onto its
own line.

### Inputs

Paper, ruled edge, `--radius`. Focus is a `--accent` outline rather than a
border change, so nothing moves when a field is focused.

### Tool group — `.toolGroup` + `.toolGroupLabel`

The palette under the map. Each kind of tool — terrain, doors and stairs,
markers, light, movement, map, the view switches — is a group under a ruled
small-caps label, separated from its neighbours by a hairline. Before this it
was a run of swatches, checkboxes and buttons with nothing saying where one
kind stopped and the next began.

The bar is a **flex row that scrolls sideways**, not floats. Floated, the last
group wrapped to a second line as soon as the movement controls appeared — and
on a bar pinned to the bottom of the window, a second line is off the screen.
Scrolling sideways loses nothing. There is a test that measures the palette at
a window too narrow to hold it.

The swatches sit inside `.nonSelected` wrappers, and `mapTool` marks a
selection by reaching for the swatch's `parentElement`, so **those wrappers must
stay the direct parent** of each swatch.

**The bar is `var(--palette-height)` tall, not a share of the sheet.** A toolbar
is as tall as the tools in it. At `height: 10%` it was 76px in an 820px-tall
window against 81px of tools, and the bottom row of view switches was cut off —
and it shrank again whenever anything else took height out of the map sheet.
`#mapContainer` takes `calc(100% - var(--palette-height))` so the two tile
exactly. There is a test that measures the bar against its tallest group.

### Staircase — `.warpTile`, `.warpPending`, `.warpTool`

**A map holds more than one level by drawing them as separate parts of the one
grid.** There is exactly one `mapArray` per room and nothing anywhere expects
otherwise, so a second level is a second room drawn further along the same
board. A staircase joins a tile in one to a tile in the other: `tile["warp"] =
[y, x]`, written on **both** ends.

The pathfinder is where this has to be taught, and it is one place. `astar`
derived neighbours from a hardcoded list of eight directions and nothing else,
so a link is simply a ninth neighbour, added when the tile you are standing on
has one. It costs **one square** — the cost rule reads the two coordinates to
tell a diagonal from a straight step, and the ends of a staircase differ in both
without being diagonal, so a warp step is flagged and charged straight.

`warp_heuristic` is the part that is easy to miss. The estimate was the distance
across the map, which for two levels side by side is enormous, so a unit at the
top of the stairs with its target one square past the bottom was told the long
way round was closer, walked it, and was charged for every square. The estimate
now also considers going by way of each staircase.

The far end is checked for walkable and seen, and **nothing else**. The wall
checks a normal step makes are about which side of a square you cross, and a
staircase is not crossed from any side — a wall between the two ends means
nothing, since they were never next to each other.

**Both ends are let go together.** Painting over a staircase, relinking one end
somewhere else, or clicking the same square twice all clear the pair; a tile
left pointing at a partner that no longer points back is a staircase to nowhere,
still drawn as one.

**Players are told about a staircase only where they have been.** The mark is
stripped from unseen squares and from secret ones, in `player_map` and in the
in-place mask `map_edit` uses — that mask edits rather than rebuilds, so
anything not explicitly dropped reaches the players. A mark in the fog would
show a way through where the fog says there is nothing, and name the square at
the other end besides.

The tool is **two clicks, not a paint**: a staircase is a pair. The first click
marks its square `.warpPending` in `--danger`, dashed, because it is not a
staircase yet; the second finishes it or, on the same square, takes an existing
one out. Changing tool abandons a half-made pair rather than leaving it to join
itself to whatever is clicked next. A finished pair is ringed in `--accent` —
*chosen*, in the sense of spoken for — as an inset ring rather than a fill, so
the stair art, the floor and any lit wash still read underneath.

### Spell link and spell sheet — `.spellLink`, `#spellSheet`

A spell's name, wherever it is listed, opens its full entry. Marked the way a
reference in a book is — the accent colour with a dotted rule under it — and
**not as a button**: these sit in the middle of a line of prose, and a row of
buttons there would read as things to press rather than as the list it is.

The entry opens in a lifted dialog rather than a panel: both views want it and
neither has room to keep it open. `formatSpellObj` builds the body, so the
picker and the dialog show a spell the same way; its leading name line is
hidden inside `#spellSheetBody` because the dialog's heading already says it.

The two sides reach it differently. **The player's own spells are whole rows
out of the spells table**, kept in `spellcasting` since they were chosen, so
clicking one opens the entry with nothing fetched. **A creature's statblock
gives only a name**, so the GM side looks it up — and the name has to be dug
out of how print writes it: `greater dispel magic (DC 22)UM` is the table's
`Dispel Magic, Greater`. `spell_name_candidates` handles the brackets, the
source-book superscript, the slot markers glued to the word, and the rank that
belongs at the back. About one name in fourteen still finds nothing, and most
of those are **class features rather than spells** — a cleric's touch of evil,
a wizard's force missile — which have no row and never will. The dialog says
that rather than showing an empty entry.

Lists split with `splitSpellList`, which respects brackets: naively, `dispel
evil (2, DC 22)` becomes two spells, one of them called `DC 22)`. The server
splits the same way, in `split_spell_list`, for the same reason.

**In a statblock** — the picker's preview and the unit sheet's entry, both built
by `statblockElement` — the spell lines are drawn by `appendSpellList`, which
finds the group markers with `SPELL_GROUP` and makes links of what lies between
them. Everything else stays as text, so the line still reads the way it does in
the book: `Spells Known (CL 7th; concentration +12)`, then `3rd (5/day)—` in
front of its spells. A line with no group marker in it is left alone entirely —
nothing there says which words are spells. `Domains` is excluded by name:
`Evil, Water` are domains, and looking them up as spells would find nothing
every time.

`#spellModal` is the dialog's own id, and it removes itself by reference. The
creature picker is a modal too and owns `#modalBackground`; while they shared
that id, `getElementById` found the picker first, so shutting a spell opened
from inside the picker shut the picker instead and threw away the search that
got there. It carries a higher `z-index` than `.modal` for the same reason.

### Creature panel — `#bottomDiv` on the GM view

The GM's counterpart to the player's action bar, in the same place and opened by
the same kind of tab: the creature the GM is running, under the map they are
running it on. Its heading is the creature's name; under that a strip of HP, AC
and initiative, then attacks and spells in two columns that scroll separately.

It shows **whatever is selected, and failing that whoever's turn it is**, so a
GM can read one creature's attacks while another is up. The attack and casting
rows are the same `attackRow` and `castingRow` the unit sheet builds, so the
roll and cast buttons work here without anything new behind them. `readAttacks`
is scoped to the `#unitAttacks` container, which is why a second set of rows on
the page is safe.

A unit carries AC only as the pieces it is added up from, so for a creature out
of the bestiary the figure is read from the cached record, and for one made by
hand it stays blank rather than showing a wrong total.

### Save roll — `.saveRoll`

A saving throw is a thing the GM or the player *does* rather than a figure they
read, so the saves at the end of the stat strip are buttons rather than text —
and each carries its modifier on its face, `Fort +13`, so the button says what
it will add before it is pressed. That is the same call the attack rows make by
keeping the bonus in a box beside the roll.

**A save that is not written down gets no button**, rather than a `+0` one that
would be a roll meaning nothing. A unit made by hand has no bestiary entry at
all and shows an em dash, `.mobStatNone` — never a zero, which reads as a real
modifier. `parseSaves` reads `Fort +13, Ref +9, Will +14` off the record, and
the server parses the same shape in `parse_saves` — this side needs it too
because the number goes back with the roll. 10,324 of the 10,332 creatures give
up all three.

The player's three sit beside the totals on their sheet and roll **from the
total, not the parts under it**, so a player who has just corrected a number and
pressed roll gets the number they are looking at.

**Who sees it follows who rolled**, the rule attack rolls already go by, and it
matters more here: the party learning that the lich made its save is the game,
learning that it made it by eleven is not. A monster's save goes to the GM's
views alone; a player's goes to the shared chat and to the GM. The server checks
that a player only rolls for something they control, and that the save is one of
the three names it knows — that string ends up in everyone's chat.

**Special abilities are folded away behind a button in the heading.** They are
the longest thing about a creature and the panel is a quarter of the window, so
they stay shut until something actually uses one. Unfolded they are **laid over
the two columns, not pushed in above them** — opening the fold must not move the
roll buttons out from under the pointer — and the stat strip sits outside the
stack they cover, so HP and AC stay on screen either way. The entries come from
`specialAbilityLines`, the same builder the statblock uses, so a name and its
`(Ex)`/`(Su)`/`(Sp)` tag read the same in both places. On a unit with no
bestiary entry the button is **disabled with a reason in its title** rather than
absent, the way an unrollable attack keeps its dead button. The fold shuts
itself when the panel changes creature, and stays as it is otherwise — an update
arrives whenever anything moves, and shutting on each one would make it
unusable.

Description is deliberately not here. It is flavour rather than something a GM
reaches for mid-round, and most imported creatures carry none, so a slot for it
would be empty more often than not. It is on the full statblock.

**The panel belongs to the map, and so does its handle.** The handle sits
outside `#activeTabDiv` — it has to, since `.mapSheet` clips its contents and
the tab straddles that edge — so the loop in `enableTab` that hides the other
tabs never reached it, and a tab offering to open the creature panel sat at the
foot of the character sheet and the lore pages. `enableTab` now shows it only
for `mapWrapper`. The player's action-bar handle is the same element in the same
place and gets the same treatment; `#leftPopButton` deliberately does not, since
it opens the left-hand column, which is the whole page's rather than the map's.

**The panel has three heights, and its tabs are how you move between them.**
Shut, a quarter of the window, and the whole of it with the map behind. A
quarter is enough to run a turn from — the attacks and the HP — and not enough
to read a caster's spell list in, which is what the full height is for.

The tabs follow from that: **shut there is one**, and it opens the panel; **open
there are two**, one to shut it and one to take it full height, that being the
only state with a step to take in both directions; **full height there is one
again**, and it drops back to the open height rather than shutting. No tab ever
skips a step. Both tabs are the same size on the same edge, so the pair reads as
two tabs on one panel rather than as a tab and a button.

Full height needs `#activeTabDiv` to get a **stacking context of its own**. The
palette is `z-index: 5` and lives inside the map sheet, so it painted straight
through the expanded panel — a row of terrain swatches across the middle of a
spell list. A stacking context confines that 5 to the holder. Raising the panel
above 5 instead would have put it over the tab that shuts it.

The height **resets to the quarter when the panel shuts**, since the panel opens
itself on the GM's turn and the map vanishing at the top of every one of those
is not what anyone asked for.

**`.castingList` must not scroll inside the panel.** It caps itself at 260px for
the unit sheet, where it sits in a page that scrolls as a whole and would
otherwise run for three thousand pixels. In the panel the column around it
scrolls already, so the cap gave a caster a scrollbar inside a scrollbar with
part of the list in each. `#mobPanelCastings .castingList` lifts it.

**It opens itself when initiative reaches a creature the GM runs.** That is the
moment its attacks are wanted, so the panel is offered rather than waited for.
Three rules keep that from becoming a nuisance: only for `controlledBy == "gm"`,
because a player's turn is the player's to take; only when the map is the tab on
screen, since off it there would be no handle to shut the panel with; and **only
once per turn**, so a GM who puts it away has it stay away while units move
about — an update arrives every time one does.

The turn is identified as `roundCount:initiativeCount`, not by the creature. With
a short initiative order, going round brings the same creature back, and keying
on the creature meant the panel never opened again after the first round.

The effect placer borrows this panel, and its table goes in `#bottomEffectHolder`
inside the body rather than at the panel's root. It used to write a height
straight onto `#activeTabDiv`, which outranked the class the tab toggles and
left the panel unable to make room for itself afterwards; it calls
`showBottomDiv`/`hideBottomDiv` now, so there is one way to open this thing.

### Pull tab — `#leftPopButton`, `#bottomPopupButton`

The two handles that open and shut the player's side panel and action bar. Each
is a **tab joined to the thing it opens**: tinted like a panel heading, ruled on
three sides, rounded only on the outer corners, and with **no border at all on
the side it meets**. That last part is what makes it read as attached rather
than as a button that happens to be nearby.

Shut, the action bar's tab sits flush with the foot of the window, under the map
sheet — the bar is off-screen and its tab is the only part still showing. Open,
it fills the gap between the sheet and the bar exactly, so it never climbs over
the sheet's bottom edge.

The tab has to live **with the panel, not inside the map sheet**: `.mapSheet` is
`overflow: hidden`, so a handle placed in it is clipped at the join it is meant
to straddle.

### Tab bar

An ink bar with paper tongues. The open tab is solid `--paper` with `--ink`
text; the rest are a 10% wash of paper on the ink.

**The bar is `height: 40px` with `box-sizing: border-box`.** Everything below is
laid out against `calc(100% - 40px)`, so a 41px bar pushes the map a pixel out
of the window — and a one-pixel overflow was enough to break the battlemap
alignment drag. There is a test for this.

`enableTab` sets `.tabActive` from each tab's `data-tab` attribute. Before this
nothing on screen said which tab you were on.

### Statblock — `.sb*`

Unchanged; it is where all of the above came from. It now draws `--sbInk` and
`--sbRule` from the shared tokens rather than defining them again.

## What the language does not cover

**Map tile artwork is content, not chrome.** The walls, doors and stairs are
drawn with gradients in pure black, and the light-level swatches are literal
colour samples. These are the *subject*, the way the ink on a printed map is,
and they do not follow the chrome palette. The secret-tile and alignment-mode
markers stay red for the same reason: they are signals, not decoration.

**Overlays keep their existing discipline.** From the light and discovered
washes, which cost real debugging to get right:

- Never touch a tile's `background` — that belongs to its type.
- Never touch a tile's `opacity` — that belongs to Show Features.
- Always set `pointer-events: none`.
- Always clear unconditionally on redraw.
- A dark wash must stack **above** the tile. `.mapTile` is `z-index: 2`; behind
  it, fully opaque black comes out mid-grey through 0.6 opacity.

## Working on this

**Panels that JavaScript rewrites cannot be styled in the template.**
`gm_update` replaces the whole of `#links`; `updateLore` replaces the whole of
`#lorePage`. Anything put in the markup there is wiped on the first update, so
the heading and the field labels have to be built in the JavaScript that builds
the rest.

**The shell must not overflow by so much as a pixel.** `.screenDiv` is a
column flex box, not a stack of blocks, because whitespace between the tab bar
and the page below it formed an anonymous line box that made it one pixel taller
than the window. One pixel is enough for a scrollbar, and the tab panels run the
full width, so the scrollbar landed on top of one. Flex containers ignore
whitespace-only text between their children.

**Headless Chromium draws overlay scrollbars, which take no width.** That is
why every measurement said the panel fitted while it sat under a real scrollbar
in a real browser. Assert on the *overflow* — `scrollHeight - clientHeight` —
rather than on whether one box overlaps another, because the overflow is visible
either way.

**A tooltip cannot escape a box that scrolls.** `#mapTools` scrolls sideways,
and a box that scrolls on one axis clips the other, so the palette's tooltips
open *below* their swatch, inside the bar, rather than above it.

**Look at it.** Two of the worst defects in this codebase's history were
invisible to a green test suite: a light wash that rendered mid-grey while every
class and colour assertion passed, and a control that opened six pixels below
the fold while `is_visible` returned `True`. The statblock panel on the unit
sheet repeated the second one before it was moved beside the fields.

Assert on **where things land**, not only on whether they exist. A bounding box
inside the viewport is a real test; `display !== "none"` is not.
