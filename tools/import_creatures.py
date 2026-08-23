"""Merge a PFSRD creature CSV into the bundled creatures table.

Run once to produce the mudfinder.sql that ships with the app; the database is a
bundled asset rather than user state, so this is not a migration the server runs
at startup.

    python tools/import_creatures.py monsters.csv
    python tools/import_creatures.py https://example.invalid/monsters.csv

The two datasets this was written for share a schema but not a curation. The
bundled table is the core bestiary -- Gnome, Intellect Devourer, Blue Whale,
Dire Ape. The CSV is heavier on named NPCs and adventure-path statblocks --
Faydreth Zaine, Bridge Guard, Marine Officer. They overlap by only a few hundred
names, so this keeps both rather than replacing one with the other.

Three things happen to the data on the way in, each explained where it is done:
FullText becomes a readable Description, FullText itself is dropped, and a
normalised creature type is added so the picker can offer a type filter.
"""

import argparse
import csv
import html
import os
import re
import sqlite3
import sys
import urllib.request

DEFAULT_DATABASE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "mudfinder.sql")

# Creatures are matched by name alone, case-folded, and only against the rows
# that were already in the table -- the bundled curation always wins.
#
# Not (Name, CR, Source), which is the obvious key and the wrong one: Source
# means different things in the two files. The bundled table records the
# rulebook ("PFRPG Bestiary"), the CSV records the adventure a statblock was
# printed in ("Rappan Athuk-Level 12A"). Keying on it matched almost nothing,
# and every shared name imported a second time -- two identical Goblins, and a
# GM typing "goblin" having to guess between them.
#
# The CSV is deliberately not folded against itself. Two different "Bridge
# Guard" NPCs in two different adventures are two real statblocks, and the
# picker shows Source so they can be told apart.
#
# The id columns cannot be used for any of this: the two sources number
# independently and share no values at all.
def dedup_key(row):
    return (row.get("Name") or "").strip().lower()

# The Pathfinder creature types, longest first so that "monstrous humanoid"
# matches before "humanoid" does.
CREATURE_TYPES = sorted([
    "aberration", "animal", "construct", "dragon", "elemental", "fey",
    "humanoid", "magical beast", "monstrous humanoid", "ooze", "outsider",
    "plant", "undead", "vermin",
], key=len, reverse=True)

# Every column dropped or added by this import, so the intent is in one place.
DROPPED_COLUMNS = ("FullText",)
ADDED_COLUMNS = ("TypeNorm",)

# No index on Name: the search is a substring match, and a leading wildcard
# cannot use one. These two serve the CR and type filters, which are equality.
INDEXES = (
    ("creatures_cr", "CR"),
    ("creatures_typenorm", "TypeNorm"),
)


def normalise_type(raw):
    """The creature type as one of CREATURE_TYPES, or "" if it is none of them.

    The Type column is free text and inconsistent in both sources: "Humanoid"
    beside "humanoid", "advanced magical beast", "augmented plant", "animal
    companion 13", and one row reading "female pit fiend-bound human sorcerer 13
    humanoid". A filter over the raw values is unusable, and matching a known
    type inside the string covers every row in both datasets.
    """
    lowered = (raw or "").lower()
    for creature_type in CREATURE_TYPES:
        if creature_type in lowered:
            return creature_type
    return ""


def flavour_text(name, full_text):
    """The prose at the top of a FullText statblock, if it has any.

    FullText is a rendered HTML statblock and it is mostly a *renderer*: every
    line of it comes from a column that is already here, so keeping the whole
    thing would be 13 MB to say what CR, HP, Senses and the rest already say.
    Measured over the CSV, 6,649 of its rows strip down to exactly that and
    around 77 open with real prose that exists nowhere else:

        The stone treant is a variant of the treant native to the Plane of
        Earth. They are very rare even there, located in isolated pockets...

    So the re-renders are thrown away and the prose is kept. A statblock is
    recognised by how it opens -- the creature's name, then its CR -- and the
    picker draws its detail pane from the columns whenever this comes back
    empty, which is the overwhelming majority of imported rows.
    """
    text = statblock_text(full_text)
    if not text:
        return ""
    if re.match(r"^%s\s*\n?CR\b" % re.escape((name or "").strip()), text[:120]):
        return ""
    return text


def statblock_text(full_text):
    """FullText with its markup taken off."""
    if not full_text:
        return ""
    # Element and all for the two that carry content rather than describe it.
    # The closing tags allow whitespace before the bracket -- "</script >" is
    # valid HTML, and a pattern that misses it leaves the tag behind. Nothing
    # here is a security boundary: the result is stored as text and rendered
    # with textContent, never as markup, and the catch-all below would strip
    # what survived anyway. It is written properly because it is cheap to.
    text = re.sub(r"<link\b[^>]*>|<script\b[^>]*>.*?</script\s*>|<style\b[^>]*>.*?</style\s*>",
                  "", full_text, flags=re.S | re.I)
    # The block tags are where the line breaks belong; everything else goes.
    text = re.sub(r"</(h5|div|p|tr|li)\s*>", "\n", text, flags=re.I)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n\s*\n+", "\n", text).strip()


def read_csv(source):
    """Rows from a path or a URL. The field size limit is raised because a
    single FullText cell runs to tens of kilobytes."""
    csv.field_size_limit(min(sys.maxsize, 2 ** 31 - 1))
    if source.startswith("http://") or source.startswith("https://"):
        with urllib.request.urlopen(source) as response:
            text = response.read().decode("utf-8", "replace")
        return list(csv.DictReader(text.splitlines()))
    with open(source, newline="", encoding="utf-8", errors="replace") as handle:
        return list(csv.DictReader(handle))


def table_columns(connection, table):
    return [row[1] for row in connection.execute("PRAGMA table_info(%s)" % table)]


def rebuild_table(connection, columns):
    """Rewrite creatures with FullText gone and TypeNorm added.

    SQLite can drop a column in place these days, but rebuilding is the portable
    way and this has to run once, offline, on a file the app ships.
    """
    kept = [c for c in columns if c not in DROPPED_COLUMNS]
    new_columns = kept + [c for c in ADDED_COLUMNS if c not in kept]
    quoted = ", ".join('"%s"' % c for c in new_columns)
    connection.execute("CREATE TABLE creatures_new (%s)" % ", ".join('"%s" TEXT' % c
                                                                    for c in new_columns))
    connection.execute(
        "INSERT INTO creatures_new (%s) SELECT %s, '' FROM creatures"
        % (quoted, ", ".join('"%s"' % c for c in kept)))
    connection.execute("DROP TABLE creatures")
    connection.execute("ALTER TABLE creatures_new RENAME TO creatures")
    return new_columns


def import_creatures(database, source, verbose=True):
    rows = read_csv(source)
    connection = sqlite3.connect(database)
    try:
        original_columns = table_columns(connection, "creatures")
        if any(column in original_columns for column in ADDED_COLUMNS):
            raise SystemExit(
                "%s has already been imported into (it has %s). Start from a "
                "pristine copy: git checkout %s"
                % (database, ", ".join(ADDED_COLUMNS), os.path.basename(database)))
        before = connection.execute("select count(*) from creatures").fetchone()[0]
        columns = rebuild_table(connection, original_columns)

        # Only the rows that were here first, so the bundled curation wins and
        # the CSV is never folded against itself.
        existing = {(row[0] or "").strip().lower()
                    for row in connection.execute("select Name from creatures")}

        added = skipped = 0
        for row in rows:
            key = dedup_key(row)
            if key in existing:
                skipped += 1
                continue
            values = {column: (row.get(column) or "") for column in columns}
            values["Description"] = row.get("Description") or flavour_text(row.get("Name"),
                                                                          row.get("FullText"))
            values["TypeNorm"] = normalise_type(row.get("Type"))
            connection.execute(
                "INSERT INTO creatures (%s) VALUES (%s)"
                % (", ".join('"%s"' % c for c in columns), ", ".join("?" * len(columns))),
                [values[c] for c in columns])
            added += 1

        # Every row, imported or not, needs a normalised type for the filter.
        for creature_id, raw_type in list(connection.execute(
                "select rowid, Type from creatures where coalesce(TypeNorm, '') = ''")):
            connection.execute("update creatures set TypeNorm = ? where rowid = ?",
                               (normalise_type(raw_type), creature_id))

        # Renumber so id is a usable key across both sources. They arrived with
        # separate numbering schemes that happened to collide.
        connection.execute("update creatures set id = rowid")

        for name, column in INDEXES:
            connection.execute('CREATE INDEX IF NOT EXISTS %s ON creatures ("%s")' % (name, column))

        connection.commit()
        # Outside the transaction, and the reason the file does not grow by the
        # size of the column that was just dropped.
        connection.isolation_level = None
        connection.execute("VACUUM")

        after = connection.execute("select count(*) from creatures").fetchone()[0]
        if verbose:
            print("read %d rows from %s" % (len(rows), source))
            print("added %d, skipped %d already present" % (added, skipped))
            print("creatures: %d -> %d" % (before, after))
            print("dropped %s, added %s" % (", ".join(DROPPED_COLUMNS), ", ".join(ADDED_COLUMNS)))
            print("database now %.1f MB" % (os.path.getsize(database) / 1e6))
        return {"read": len(rows), "added": added, "skipped": skipped,
                "before": before, "after": after}
    finally:
        connection.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("source", help="path or URL of the creature CSV")
    parser.add_argument("--database", default=DEFAULT_DATABASE,
                        help="the SQLite file to merge into (default: the bundled one)")
    args = parser.parse_args()
    import_creatures(args.database, args.source)


if __name__ == "__main__":
    main()
