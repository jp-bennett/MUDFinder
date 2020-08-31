import copy
from unit import Unit
from player import Player
from flask_socketio import emit
from math import floor



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

    def insert_initiative(self, creature):
        if not creature.initiative: return
        if len(self.initiativeList) == 0:
            self.initiativeList.insert(0, creature)
            initNum = 0
            for x in self.initiativeList:
                x.initNum = initNum
                initNum += 1
            return
        for x in range(len(self.initiativeList)):
            if int(self.initiativeList[x].initiative) <= int(creature.initiative):
                self.initiativeList.insert(x, creature)
                initNum = 0
                for x in self.initiativeList:
                    x.initNum = initNum
                    initNum += 1
                return
        self.initiativeList.append(creature)
        initNum = 0
        for x in self.initiativeList:
            x.initNum = initNum
            initNum += 1

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
            playerObject["initiativeList"] = tmpinitiativeList
        else:
            playerObject["initiativeList"] = []
        for i in range(len(self.unitList)):
            if self.unitList[i].controlledBy != "gm" or (
                    self.unitList[i].location != [-1, -1] and self.mapData["mapArray"][self.unitList[i].location[0]][self.unitList[i].location[1]]["seen"]):
                playerObject["unitList"].append(self.unitList[i].to_json())
        return playerObject

    def player_map(self):
        tmpMapData = {}
        tmpMapData["mapBackground"] = self.mapData["mapBackground"]
        tmpMapData["showBackground"] = self.mapData["showBackground"]
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
        path = astar(self.mapData["mapArray"], (tmpUnit.y, tmpUnit.x), end, maxMove, ignoreSeen)
        if path is None:
            return
        tmpUnit.distance += path.pop(0)
        for x in path:
            tmpUnit.movePath.append(x)
        tmpUnit.location = path[-1]
        tmpUnit.y = path[-1][0]
        tmpUnit.x = path[-1][1]
        return

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
                        if self.mapData["mapArray"][cells[distance][1]][cells[distance][0]]["seen"] == False:
                            mark = True
                        self.mapData["mapArray"][cells[distance][1]][cells[distance][0]]["seen"] = True
                        if mark:
                            changedTiles.append(self.mapData["mapArray"][cells[distance][1]][cells[distance][0]])
                            mark = False
                        if not self.mapData["mapArray"][cells[distance][1]][cells[distance][0]]["walkable"]:
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

        def __eq__(self, other):
            return self.position == other.position

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

        # Loop through children
        for child in children:

            # Create the f, g, and h values
            if child.position[0] != current_node.position[0] and child.position[1] != current_node.position[1]:
                child.g = current_node.g + 1.5
            else:
                child.g = current_node.g + 1
            child.h = abs(child.position[0] - end_node.position[0]) + abs(child.position[1] - end_node.position[1])
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
    return True


def default(local_dict, key, local_default):
    if key in local_dict:
        return local_dict[key]
    else:
        return local_default