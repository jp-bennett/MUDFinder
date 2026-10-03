import copy
from unit import Unit
from player import Player
from flask_socketio import emit
from math import floor


# How an uploaded battlemap image is placed behind the grid, measured in grid
# squares rather than pixels so the numbers survive a change of tile size.
# backgroundTilesWide is how many squares the image spans across; the offsets
# are where its top left corner sits relative to tile (0, 0), and may be
# negative. A map with none of these set is drawn the old way, stretched to
# fill the play area, which is what every map made before this existed wants.
BACKGROUND_ALIGNMENT_KEYS = ("backgroundTilesWide", "backgroundOffsetX", "backgroundOffsetY")

# Stamped on the map every time the alignment is written, and carried with it.
# It is what lets a client tell a payload older than the alignment it is already
# showing from one that is newer. A full map sent in answer to a grid resize
# carries the alignment as it stood when that resize was handled, which may be
# behind what the GM has dragged the image to since.
BACKGROUND_ALIGNMENT_SEQ = "backgroundAlignmentSeq"


# What a player is sent in place of a creature in the initiative order that
# their party cannot see. It holds every field the client reads off an entry
# and nothing else -- no name, no count, no position -- so the players know a
# turn is passing without learning whose.
def sees_through(tile):
    """Whether sight carries on past a square that cannot be walked through.

    A window, a portcullis, a chasm edge, a wall of force: it stops the move
    and not the look. Sight and movement were the same question until now --
    the ray stopped on `walkable`, so every square that turned a creature back
    also hid whatever was behind it.

    A secret square is excluded however it is marked. One is masked to the
    players as the wall it is pretending to be, and a ray carrying on through
    it would show them the room behind a door they have not found -- which is
    the tell the mask exists to prevent.
    """
    return bool(tile.get("transparent")) and not tile.get("secret")


# A thin door sits on the edge between two squares, the way a thin wall does,
# and both squares carry it: the "left" of one is the "right" of its
# neighbour. Keeping both in step is what lets either square be asked about a
# crossing without having to look at the other.
#
# Three states, and a fourth in the absence of the key -- no door on that edge
# at all -- so a map drawn before any of this existed needs nothing doing to
# it.
DOOR_OPEN = "open"
DOOR_CLOSED = "closed"
DOOR_LOCKED = "locked"
DOOR_STATES = (DOOR_CLOSED, DOOR_OPEN, DOOR_LOCKED)

OPPOSITE_SIDE = {"left": "right", "right": "left", "top": "bottom", "bottom": "top"}
SIDE_OFFSET = {"left": (0, -1), "right": (0, 1), "top": (-1, 0), "bottom": (1, 0)}


def door_on(tile, side):
    """The thin door on one edge of a square, or None where there is none."""
    doors = tile.get("doors")
    if not doors:
        return None
    return doors.get(side)


def door_stops_movement(tile, side):
    """Only a locked one.

    A shut door is walked through rather than around: the move opens it, the
    same as ordering a creature onto a door that fills a whole square. Locked
    is the one that turns a creature back.
    """
    return door_on(tile, side) == DOOR_LOCKED


def door_stops_sight(tile, side):
    """Anything that is not standing open.

    A shut door is as opaque as the wall it is set into. See-through is a
    detail of a square rather than of an edge, so a portcullis across a
    doorway cannot be spelled yet -- that wants the transparent detail
    extended to edges, which is its own piece of work.
    """
    return door_on(tile, side) in (DOOR_CLOSED, DOOR_LOCKED)


def set_door(tile, side, state):
    """Put a thin door on an edge, or take it off with state None.

    The key goes when the last door does, so that a square with no doors is
    spelled one way rather than two.
    """
    doors = tile.get("doors")
    if state is None:
        if doors:
            doors.pop(side, None)
            if not doors:
                tile.pop("doors", None)
        return
    if doors is None:
        doors = tile["doors"] = {}
    doors[side] = state


def entry_sides(previous, current):
    """Which sides of `current` a step from `previous` crosses.

    Both are (y, x). A diagonal crosses two of them, which is why this is a
    list -- a step up and to the left enters through the bottom edge and the
    right edge at once, and either can be the one that stops it.
    """
    sides = []
    if current[0] - previous[0] == -1:
        sides.append("bottom")
    elif current[0] - previous[0] == 1:
        sides.append("top")
    if current[1] - previous[1] == -1:
        sides.append("right")
    elif current[1] - previous[1] == 1:
        sides.append("left")
    return sides


def masked_initiative_entry():
    return {
        "charName": "?",
        "initiative": "",
        "controlledBy": "",
        "unitNum": -1,
        "x": -1,
        "y": -1,
        "movePath": [],
        "distance": 0,
        "size": "medium",
        "color": "black",
    }


class Session(object):

    def __init__(self, room, gmKey, name):
        self.room = room
        self.gmKey = gmKey
        self.gmRoom = ""
        self.name = name
        self.inInit = False
        self.initiativeCount = 0  # current spot in itiative. Tracks whos turn it is.
        self.roundCount = 0  # current round. Starts at 0 for surprise, 1 for first round
        self.playerList = {}  # Will become less important
        self.unitList = []  # new master list, start removing all the rest.
        self.initiativeList = []
        self.savedEncounters = {}
        self.mapData = {}
        self.mapData["mapArray"] = []
        self.mapData["showBackground"] = True
        self.mapData["mapBackground"] = "static/images/mapbackground.jpg"
        self.movePath = []
        self.lore = []
        self.loreFiles = {}
        self.images = {}
        self.effects = []

    def to_json(self):  # need a full version for saves, and a partial version for updates
        """Serialize object to JSON"""
        keyNames = []
        for key in self.savedEncounters.keys():
            keyNames.append(key)

        tmpplayerList = {}
        for x in self.playerList:
            tmpplayerList[x] = self.playerList[x].to_json()

        tmpunitList = []
        for x in self.unitList:
            tmpunitList.append(x.to_json())

        tmpinitiativeList = []
        for x in self.initiativeList:
            tmpinitiativeList.append(x.to_json())

        return {
            "room": self.room,
            "gmKey": self.gmKey,
            "name": self.name,
            "inInit": self.inInit,
            "initiativeCount": self.initiativeCount,
            "roundCount": self.roundCount,
            "playerList": tmpplayerList,
            "unitList": tmpunitList,
            "initiativeList": tmpinitiativeList,
            "movePath": self.movePath,
            "savedEncounters": keyNames,
            "effects": self.effects
        }

    def gen_save(self):
        """Serialize object to JSON"""
        tmpplayerList = {}
        for x in self.playerList:
            tmpplayerList[x] = self.playerList[x].to_json()

        tmpunitList = []
        for x in self.unitList:
            tmpunitList.append(x.to_json())

        tmpinitiativeList = []
        for x in self.initiativeList:
            tmpinitiativeList.append(x.to_json())
        return {
            "room": self.room,
            "gmKey": self.gmKey,
            "gmRoom": self.gmRoom,
            "name": self.name,
            "inInit": self.inInit,
            "initiativeCount": self.initiativeCount,
            "roundCount": self.roundCount,
            "playerList": tmpplayerList,
            "unitList": tmpunitList,
            "initiativeList": tmpinitiativeList,
            "mapData": self.mapData,
            "movePath": self.movePath,
            "savedEncounters": self.savedEncounters,
            "lore": self.lore,
            "loreFiles": self.loreFiles,
            "images": self.images,
            "effects": self.effects
        }

    def from_json(self, obj):
        self.name = obj["name"]
        self.inInit = obj["inInit"]
        self.initiativeCount = obj["initiativeCount"]
        self.roundCount = obj["roundCount"]
        for x in obj["unitList"]:
            if x["type"] == "player":
                self.unitList.append(Player(x))
                self.playerList[x["charName"]] = self.unitList[-1]
            else:
                self.unitList.append(Unit(x))
            if self.unitList[-1].inInit:
                self.initiativeList.append(self.unitList[-1])
        if "mapData" in obj:
            self.mapData = obj["mapData"]
        else:
            self.mapData["mapArray"] = obj["mapArray"]
        if "showBackground" not in self.mapData:
            self.mapData["showBackground"] = True
        if "mapBackground" not in self.mapData:
            self.mapData["mapBackground"] = "static/images/mapbackground.jpg"
        # Saves written before background alignment existed have none of these.
        # Leaving them absent is deliberate: the client falls back to the old
        # stretch-to-fill rendering when they are missing, so those maps look
        # exactly as they always did.
        self.lore = obj["lore"]
        if "loreFiles" in obj.keys():
            for x in obj["loreFiles"]:
                self.loreFiles[int(x)] = obj["loreFiles"][x]
        self.savedEncounters = obj["savedEncounters"]
        self.images = default(obj, "images", {})
        self.number_units()
        self.effects = default(obj, "effects", [])
        self.gmRoom = default(obj, "gmRoom", "")
        self.order_initiative_list()
        return

    def order_initiative_list(self):
        tmp = ""
        if self.inInit:
            tmp = self.initiativeList[self.initiativeCount].charName
        self.initiativeList.sort(key=lambda i: int(i.initiative), reverse=True)
        initNum = 0
        for x in self.initiativeList:
            x.initNum = initNum
            initNum += 1
        if self.inInit:
            if self.inInit and tmp != self.initiativeList[self.initiativeCount].charName:
                self.initiativeCount += 1

    def number_units(self):
        for x in range(len(self.unitList)):
            self.unitList[x].unitNum = x

    def renumber_initiative(self):
        """initNum is a creature's place in the order, and the client indexes
        the list by it, so it has to be redone whenever the order changes."""
        for position, creature in enumerate(self.initiativeList):
            creature.initNum = position

    def await_initiative(self, creature):
        """Give a creature a slot in the order with no score in it yet.

        The GM asks the party for initiative and the party rolls at their own
        pace; before this, a character simply was not in the list until their
        number arrived, so the GM had no way to see who they were waiting on
        and nowhere to type a number a player had called across the table.

        The slot goes at the foot of the list and stays there until it has a
        score. inInit is deliberately left alone: it means "has taken a place
        in the order", which this creature has not done yet, and the player's
        prompt and send_initiative both go by it.
        """
        if creature in self.initiativeList:
            return
        creature.awaitingInit = True
        # Blank rather than 0, so the row shows an empty box instead of a score
        # the creature has not rolled.
        creature.initiative = ""
        self.initiativeList.append(creature)
        self.renumber_initiative()

    def insert_initiative(self, creature):
        if not creature.initiative:
            return
        creature.awaitingInit = False
        if creature in self.initiativeList:
            self.initiativeList.remove(creature)
        # Above the first creature it beats -- and above every creature still
        # waiting on a roll, whatever is in their slot.
        position = len(self.initiativeList)
        for x in range(len(self.initiativeList)):
            entry = self.initiativeList[x]
            if entry.awaitingInit or int(entry.initiative) <= int(creature.initiative):
                position = x
                break
        self.initiativeList.insert(position, creature)
        self.renumber_initiative()

    def player_json(self):
        tmpplayerList = {}
        for x in self.playerList:
            tmpplayerList[x] = self.playerList[x].to_json()

        tmpinitiativeList = []
        for x in self.initiativeList:
            tmpinitiativeList.append(x.to_json())

        playerObject = {
            "unitList": [],
            "room": self.room,
            "name": self.name,
            "inInit": self.inInit,
            "initiativeCount": self.initiativeCount,
            "roundCount": self.roundCount,
            "playerList": tmpplayerList,
            # "mapArray": self.mapArray,
            "movePath": self.movePath,
            "effects": self.effects
        }  # add visible units from unitlist

        if self.inInit:
            # Kept the same length and the same order, with the creatures the
            # party cannot see replaced rather than removed. initiativeCount is
            # a plain index into this list on the client -- it decides whose
            # turn is highlighted and whether the player is shown the button to
            # end their turn -- so dropping entries would slide every index
            # after them.
            playerObject["initiativeList"] = [
                x.to_json() if self.unit_visible_to_players(x) else masked_initiative_entry()
                for x in self.initiativeList]
        else:
            playerObject["initiativeList"] = []
        for i in range(len(self.unitList)):
            if self.unit_visible_to_players(self.unitList[i]):
                playerObject["unitList"].append(self.unitList[i].to_json())
        return playerObject

    def unit_visible_to_players(self, unit):
        """Whether the party is allowed to know this creature is there.

        Anything a player runs -- their own character, a summon, a pet -- is
        theirs to see. Everything else is the GM's, and is visible only once it
        stands somewhere the party has explored.

        The test is "is it run by a player" rather than the older "is it run by
        the GM", because a creature added without a controller named at all had
        an empty string there, which is not "gm", and so was never hidden from
        anybody.
        """
        if unit.controlledBy in self.playerList:
            return True
        if unit.location == [-1, -1]:
            return False
        # Bounds checked rather than assumed. Shrinking a map moves a unit left
        # outside it off the board by setting x and y, but not the location
        # this reads, so the coordinates can point past the end of the grid. A
        # creature standing nowhere is not visible either.
        grid = self.mapData["mapArray"]
        row, column = unit.location[0], unit.location[1]
        if not 0 <= row < len(grid) or not 0 <= column < len(grid[row]):
            return False
        return bool(grid[row][column]["seen"])

    def player_map(self):
        tmpMapData = {}
        tmpMapData["mapBackground"] = self.mapData["mapBackground"]
        tmpMapData["showBackground"] = self.mapData["showBackground"]
        # Players have to be given the same alignment the GM set, or the
        # artwork will not line up with the grid they are moving on.
        for key in BACKGROUND_ALIGNMENT_KEYS:
            if key in self.mapData:
                tmpMapData[key] = self.mapData[key]
        tmpMapData["mapArray"] = []

        for y in range(len(self.mapData["mapArray"])):
            tmpMapLine = []
            for x in range(len(self.mapData["mapArray"][y])):
                tmpMapLine.append({"tile": self.mapData["mapArray"][y][x]["tile"], "walkable": self.mapData["mapArray"][y][x]["walkable"]})
                if "walls" in self.mapData["mapArray"][y][x]:
                    tmpMapLine[x]["walls"]  = self.mapData["mapArray"][y][x]["walls"]
                if self.mapData["mapArray"][y][x]["secret"]:
                    tmpMapLine[x] = {"tile": "wallTile", "walkable": False}
                if not self.mapData["mapArray"][y][x]["seen"]:
                    tmpMapLine[x] = {"tile": "unseenTile", "walkable": False}
                # After the masking, deliberately, and only where a player has
                # been. Before it, an undiscovered square would carry its light
                # level and draw the shape of an unexplored room through the
                # fog. After it, a secret door still matches the wall it is
                # pretending to be -- the one un-dimmed square in a dim wall
                # would be a tell.
                if self.mapData["mapArray"][y][x]["seen"] and "light" in self.mapData["mapArray"][y][x]:
                    tmpMapLine[x]["light"] = self.mapData["mapArray"][y][x]["light"]
                # Likewise after the masking, and for the same reason the warp
                # is: a square nobody has been to must not say what it is. Sent
                # at all because a player can see through one of these, and a
                # square drawn as solid wall with a lit room visible past it
                # reads as a bug rather than as a window.
                if (self.mapData["mapArray"][y][x]["seen"]
                        and not self.mapData["mapArray"][y][x]["secret"]
                        and self.mapData["mapArray"][y][x].get("transparent")):
                    tmpMapLine[x]["transparent"] = True
                # Likewise after the masking. A thin door is drawn on an edge
                # of the square, and an edge of a square nobody has been to
                # would draw the shape of a doorway through the fog. A secret
                # square is excluded for the reason its own mask exists: a
                # door marked on the face of what is pretending to be solid
                # wall is the tell.
                if (self.mapData["mapArray"][y][x]["seen"]
                        and not self.mapData["mapArray"][y][x]["secret"]
                        and self.mapData["mapArray"][y][x].get("doors")):
                    tmpMapLine[x]["doors"] = dict(self.mapData["mapArray"][y][x]["doors"])
                # Likewise after the masking. A staircase is drawn with a mark
                # on it, and a mark on a square nobody has been to would say
                # there is a way through where the fog says there is nothing --
                # and name the square at the other end of it besides.
                if (self.mapData["mapArray"][y][x]["seen"]
                        and not self.mapData["mapArray"][y][x]["secret"]
                        and "warp" in self.mapData["mapArray"][y][x]):
                    tmpMapLine[x]["warp"] = self.mapData["mapArray"][y][x]["warp"]
            tmpMapData["mapArray"].append(tmpMapLine)
        return tmpMapData

    def calc_path(self, tmpUnit, end, moveType):
        if not self.mapData["mapArray"][end[0]][end[1]]["walkable"]:
            return
        tmpUnit.movementSpeed = int(tmpUnit.movementSpeed)
        if tmpUnit.size == "large":
            if not self.mapData["mapArray"][end[0]-1][end[1]]["walkable"]:
                return
            if not self.mapData["mapArray"][end[0]][end[1]+1]["walkable"]:
                return
            if not self.mapData["mapArray"][end[0]-1][end[1]+1]["walkable"]:
                return
        if tmpUnit.location == [-1, -1]:
            tmpUnit.location = end
            tmpUnit.x = end[1]
            tmpUnit.y = end[0]
            return
        for unit in self.unitList:
            if unit == tmpUnit:
                continue
            if unit.location == [-1, -1]:
                continue
            if end == unit.location:
                return
        if moveType == 0:
            maxMove = 1
        elif moveType == 1:
            maxMove = tmpUnit.movementSpeed / 5
        elif moveType == 2:
            maxMove = tmpUnit.movementSpeed * 2 / 5
        elif moveType == 3:
            maxMove = -1
        else:
            tmpUnit.location = end
            tmpUnit.x = end[1]
            tmpUnit.y = end[0]
            return
        if tmpUnit.hasted and not moveType == 0:
            maxMove = min(maxMove * 2, maxMove + 6)
        maxMove -= tmpUnit.distance
        if maxMove < 0 and moveType != 3:
            maxMove = 0
        if tmpUnit.controlledBy == "gm":
            ignoreSeen = True
        else:
            ignoreSeen = False
        start = (tmpUnit.y, tmpUnit.x)
        path = astar(self.mapData["mapArray"], (tmpUnit.y, tmpUnit.x), end, maxMove, ignoreSeen)
        if path is None:
            return
        tmpUnit.distance += path.pop(0)
        for x in path:
            tmpUnit.movePath.append(x)
        tmpUnit.location = path[-1]
        tmpUnit.y = path[-1][0]
        tmpUnit.x = path[-1][1]
        # Shut doors the route went through are now standing open, and the
        # squares either side of each of them have changed. Sent from here
        # because this is what knows: the move itself reaches the clients
        # through send_updates, which carries creatures and not map squares.
        self.broadcast_tiles(self.open_doors_along([start] + path))
        return

    def open_doors_along(self, steps):
        """Open every shut thin door a path crosses; return the squares changed.

        Walking through a door is how it opens, the same as ordering a
        creature onto a door that fills a whole square. A locked one never
        reaches here, because astar will not route a path through one.

        Both squares either side of the edge are changed, since both carry the
        door, and both are returned so that either can be redrawn.
        """
        changed = []
        grid = self.mapData["mapArray"]
        for previous, current in zip(steps, steps[1:]):
            tile = grid[current[0]][current[1]]
            for side in entry_sides(previous, current):
                if door_on(tile, side) != DOOR_CLOSED:
                    continue
                set_door(tile, side, DOOR_OPEN)
                changed.append(tile)
                offset = SIDE_OFFSET[side]
                row, column = current[0] + offset[0], current[1] + offset[1]
                if 0 <= row < len(grid) and 0 <= column < len(grid[row]):
                    set_door(grid[row][column], OPPOSITE_SIDE[side], DOOR_OPEN)
                    changed.append(grid[row][column])
        return changed

    def mask_tiles(self, tiles):
        """A few changed squares as the players may see them.

        The rules player_map works by, applied to a handful of squares rather
        than to the whole board: an undiscovered square says nothing about
        itself, and a secret one says it is the wall it is pretending to be.
        """
        masked = copy.deepcopy(tiles)
        for tile in masked:
            if not tile.get("seen"):
                tile["tile"] = "unseenTile"
                tile["walkable"] = False
                for detail in ("warp", "light", "transparent", "doors", "walls"):
                    tile.pop(detail, None)
            elif tile.get("secret"):
                tile["tile"] = "wallTile"
                tile["walkable"] = False
                tile.pop("warp", None)
        return masked

    def broadcast_tiles(self, tiles):
        """Send a handful of changed squares to both views."""
        if not tiles:
            return
        update = {"showBackground": self.mapData["showBackground"],
                  "mapBackground": self.mapData["mapBackground"]}
        emit('gm_map_update', dict(update, mapArray=tiles), room=self.gmRoom)
        emit('player_map_update', dict(update, mapArray=self.mask_tiles(tiles)),
             room=self.room)

    def reveal_map(self, selectedPlayer):
        mark = False
        changedTiles = []
        if self.unitList[selectedPlayer].location == [-1, -1]: return []
        y = self.unitList[selectedPlayer].location[0]
        x = self.unitList[selectedPlayer].location[1]
        for xBox in range(-12, 14):
            for yBox in range(-12, 14):
                if xBox not in [-12, 13] and yBox not in [-12, 13]:
                    continue
                cells = raytrace(x, y, max(0, x + xBox), max(0, y + yBox), 12)
                for distance in range(len(cells)):
                    try:

                        # What the ray crosses to get into this square, rather
                        # than what the square is: a thin wall and a shut thin
                        # door both live on the edge between two squares, and
                        # stop a look that crosses that edge while leaving the
                        # square itself perfectly visible from the other side.
                        #
                        # raytrace works in [x, y]; entry_sides takes (y, x).
                        if distance > 0:
                            tile = self.mapData["mapArray"][cells[distance][1]][cells[distance][0]]
                            crossed = entry_sides(
                                (cells[distance - 1][1], cells[distance - 1][0]),
                                (cells[distance][1], cells[distance][0]))
                            if any(side in tile.get("walls", []) for side in crossed):
                                break
                            if any(door_stops_sight(tile, side) for side in crossed):
                                break
                        if self.mapData["mapArray"][cells[distance][1]][cells[distance][0]]["seen"] == False:
                            mark = True
                        self.mapData["mapArray"][cells[distance][1]][cells[distance][0]]["seen"] = True
                        if mark:
                            changedTiles.append(self.mapData["mapArray"][cells[distance][1]][cells[distance][0]])
                            mark = False
                        if (not self.mapData["mapArray"][cells[distance][1]][cells[distance][0]]["walkable"]
                                and not sees_through(self.mapData["mapArray"][cells[distance][1]][cells[distance][0]])):
                            break
                    except:
                        break
        return changedTiles

    def send_updates(self):
        emit('gm_update', self.to_json(), room=self.gmRoom)
        emit('do_update', self.player_json(), room=self.room)

def raytrace(x0, y0, x1, y1, maximum):  # https://playtechs.blogspot.com/2007/03/raytracing-on-grid.html
    distance = 0
    cells = []
    dx = abs(x1 - x0)
    dy = abs(y1 - y0)
    x = x0
    y = y0
    n = 1 + dx + dy

    if x1 > x0:
        x_inc = 1
    else:
        x_inc = -1
    if y1 > y0:
        y_inc = 1
    else:
        y_inc = -1
    error = dx - dy
    dx *= 2
    dy *= 2
    for i in range(n, 0, -1):
        if max(abs(x0-x), abs(y0-y)) + floor(.5 * min(abs(x0-x), abs(y0-y))) > maximum:
            return cells
        cells.append([x, y])
        if error > 0:
            x += x_inc
            error -= dy
        else:
            y += y_inc
            error += dx
    return cells


def warp_pairs(maze):
    """Every linked pair of tiles, as (from, to) positions.

    A staircase between two levels of a map is a pair of tiles that count as
    adjacent even though they are nowhere near each other. Both ends carry the
    link, so this lists each pair twice, once in each direction -- which is
    what the pathfinder wants, since it asks "where can I go from here".
    """
    pairs = []
    for y in range(len(maze)):
        for x in range(len(maze[y])):
            linked = maze[y][x].get("warp")
            if linked:
                pairs.append(((y, x), (linked[0], linked[1])))
    return pairs


def warp_heuristic(position, end, pairs):
    """Squares from here to the end, allowing for a staircase on the way.

    Without this the estimate is the distance across the map, which for two
    levels drawn side by side is enormous -- so a unit at the top of the stairs
    with its target one square past the bottom would be told the long way round
    was closer, walk it, and be charged for every square of it.
    """
    best = abs(position[0] - end[0]) + abs(position[1] - end[1])
    for entrance, exit_ in pairs:
        through = (abs(position[0] - entrance[0]) + abs(position[1] - entrance[1])
                   + 1
                   + abs(exit_[0] - end[0]) + abs(exit_[1] - end[1]))
        if through < best:
            best = through
    return best


def astar(maze, start, end, maxMove, ignoreSeen):
    """Returns a list of tuples as a path from the given start to the given end in the given maze"""

    class Node:
        """A node class for A* Pathfinding"""

        def __init__(self, parent=None, position=None):
            self.parent = parent
            self.position = position

            self.g = 0
            self.h = 0
            self.f = 0
            # Reached by a staircase rather than by stepping. Kept because the
            # cost below reads the two coordinates to tell a diagonal from a
            # straight step, and a warp differs in both without being one.
            self.viaWarp = False

        def __eq__(self, other):
            return self.position == other.position

    # Worked out once rather than per node: the heuristic consults every pair,
    # and a map has a handful of staircases against thousands of squares.
    pairs = warp_pairs(maze)

    # Create start and end node
    start_node = Node(None, start)
    start_node.g = start_node.h = start_node.f = 0
    end_node = Node(None, end)
    end_node.g = end_node.h = end_node.f = 0
    start_node.f = ((start_node.position[0] - end_node.position[0]) ** 2) + (
            (start_node.position[1] - end_node.position[1]) ** 2)
    # Initialize both open and closed list
    open_list = []
    closed_list = []

    # Add the start node
    open_list.append(start_node)

    # Loop until you find the end
    while len(open_list) > 0:
        # Get the current node
        current_node = open_list[0]
        current_index = 0
        for index, item in enumerate(open_list):
            if item.f < current_node.f:
                current_node = item
                current_index = index

        # Pop current off open list, add to closed list
        open_list.pop(current_index)
        closed_list.append(current_node)

        # Found the goal
        if current_node == end_node:
            path = []
            current = current_node
            totalDistance = 0
            while current is not None:
                if maxMove < 0 or current.g < maxMove + 1:
                    if totalDistance == 0:
                        totalDistance = current.g
                    path.append(current.position)
                current = current.parent
            path.append(totalDistance)
            return path[::-1]  # Return reversed path
        # Generate children
        children = []
        for new_position in [(0, -1), (0, 1), (-1, 0), (1, 0), (-1, -1), (-1, 1), (1, -1), (1, 1)]:  # Adjacent squares

            # Get node position
            node_position = (current_node.position[0] + new_position[0], current_node.position[1] + new_position[1])

            if Node(current_node, node_position) in closed_list:
                continue

            # Make sure within range
            if node_position[0] > (len(maze) - 1) or node_position[0] < 0 or node_position[1] > (
                    len(maze[node_position[0]]) - 1) or node_position[1] < 0:
                continue

            if not testStep(maze, current_node, new_position, node_position, ignoreSeen):
                continue

            # Create new node
            new_node = Node(current_node, node_position)

            # Append
            children.append(new_node)

        # And the far end of a staircase, if this tile is one. The eight
        # directions above are the whole of what the pathfinder knew about
        # adjacency, so this is the one place a link has to be taught.
        linked = maze[current_node.position[0]][current_node.position[1]].get("warp")
        if linked is not None:
            far = (linked[0], linked[1])
            if (0 <= far[0] < len(maze) and 0 <= far[1] < len(maze[far[0]])
                    and Node(current_node, far) not in closed_list
                    and testWarpStep(maze, far, ignoreSeen)):
                warp_node = Node(current_node, far)
                warp_node.viaWarp = True
                children.append(warp_node)

        # Loop through children
        for child in children:

            # Create the f, g, and h values
            if child.viaWarp:
                # A staircase is a step, so it costs one square -- not the 1.5
                # of a diagonal, which is what the test below would call it,
                # the two ends differing in both coordinates.
                child.g = current_node.g + 1
            elif child.position[0] != current_node.position[0] and child.position[1] != current_node.position[1]:
                child.g = current_node.g + 1.5
            else:
                child.g = current_node.g + 1
            child.h = warp_heuristic(child.position, end_node.position, pairs)
            child.f = child.g + child.h
            for closed_child in closed_list:
                if child == closed_child and child.f >= closed_child.f:
                    break
            else:
                for open_node in open_list:
                    if child == open_node and child.g >= open_node.g:
                        break
                else:
                    open_list.append(child)


def testWarpStep(maze, node_position, ignoreSeen):
    """Whether the far end of a staircase can be stepped onto.

    Only the destination is asked about. The wall checks a normal step makes
    are about which side of a square you are crossing, and a staircase is not
    crossed from any side -- a wall between the two ends means nothing, since
    they are not next to each other in the first place.
    """
    tile = maze[node_position[0]][node_position[1]]
    if not tile["walkable"]:
        return False
    if not tile.get("seen", True) and not ignoreSeen:
        return False
    return True


def testStep(maze, current_node, new_position, node_position, ignoreSeen):

    # test diagonal step
    if new_position[0] != 0 and new_position[1] != 0:
        if not maze[current_node.position[0]][node_position[1]]["walkable"]:
            return False
        if not maze[node_position[0]][current_node.position[1]]["walkable"]:
            return False
        #Need to test for walls on the target position, in the case of a diagonal step
        if "walls" in maze[node_position[0]][node_position[1]]:
            if new_position[1] == -1 and "right" in maze[node_position[0]][node_position[1]]["walls"]:
                return False
            if new_position[1] == 1 and "left" in maze[node_position[0]][node_position[1]]["walls"]:
                return False
            if new_position[0] == -1 and "bottom" in maze[node_position[0]][node_position[1]]["walls"]:
                return False
            if new_position[0] == 1 and "top" in maze[node_position[0]][node_position[1]]["walls"]:
                return False
        # A locked thin door on the far side of the same diagonal. A shut one
        # is not checked anywhere: walking through is what opens it, so it has
        # to be routed through first.
        for side in entry_sides((0, 0), (new_position[0], new_position[1])):
            if door_stops_movement(maze[node_position[0]][node_position[1]], side):
                return False


    #test next step for unwalkable
    if not maze[node_position[0]][node_position[1]]["walkable"]:
        return False

    #test next step for unseen terrain
    if not maze[node_position[0]][node_position[1]]["seen"] and not ignoreSeen:
        return False
    if "walls" in maze[current_node.position[0]][current_node.position[1]]:
        if new_position[1] == -1 and "left" in maze[current_node.position[0]][current_node.position[1]]["walls"]:
            return False
        if new_position[1] == 1 and "right" in maze[current_node.position[0]][current_node.position[1]]["walls"]:
            return False
        if new_position[0] == -1 and "top" in maze[current_node.position[0]][current_node.position[1]]["walls"]:
            return False
        if new_position[0] == 1 and "bottom" in maze[current_node.position[0]][current_node.position[1]]["walls"]:
            return False
    # The side of the square being left, which is the opposite of the side of
    # the one being entered. Both carry the door, so either would do; this one
    # matches the wall checks above it.
    for side in entry_sides((0, 0), (new_position[0], new_position[1])):
        if door_stops_movement(maze[current_node.position[0]][current_node.position[1]],
                               OPPOSITE_SIDE[side]):
            return False
    return True


def default(local_dict, key, local_default):
    if key in local_dict:
        return local_dict[key]
    else:
        return local_default