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
