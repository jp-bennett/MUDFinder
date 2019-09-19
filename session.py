class Session(object):

    def __init__(self, room, gmKey, name):
        self.room = room
        self.gmKey = gmKey
        self.name = name
        self.inInit = False
        self.initiativeCount = 0  # current spot in itiative. Tracks whos turn it is.
        self.roundCount = 0  # current round. Starts at 0 for surprise, 1 for first round
        self.playerList = {}  # Will become less important
        self.unitList = []  # new master list, start removing all the rest.
        self.initiativeList = []
        self.savedEncounters = {}
        self.mapArray = []  # make this a list of lists of dicts
        self.movePath = []

    def to_json(self):
        """Serialize object to JSON"""
        return {
            "room": self.room,
            "gmKey": self.gmKey,
            "name": self.name,
            "inInit": self.inInit,
            "initiativeCount": self.initiativeCount,
            "roundCount": self.roundCount,
            "playerList": self.playerList,
            "unitList": self.unitList,
            "initiativeList": self.initiativeList,
            "mapArray": self.mapArray,
            "movePath": self.movePath,
            "savedEncounters": self.savedEncounters
        }

    def from_json(self, obj):
        self.name = obj["name"]
        self.inInit = obj["inInit"]
        self.initiativeCount = obj["initiativeCount"]
        self.roundCount = obj["roundCount"]
        self.unitList = obj["unitList"]
        for x in self.unitList:
            if x["type"] == "player":
                self.playerList[x["charName"]] = x
            if "inInit" in x.keys() and x["inInit"]:
                self.initiativeList.append(x)
        self.mapArray = obj["mapArray"]
        self.savedEncounters = obj["savedEncounters"]
        self.number_units()
        return

    def order_initiative_list(self):
        tmp = ""
        if self.inInit:
            tmp = self.initiativeList[self.initiativeCount]["charName"]
        self.initiativeList.sort(key=lambda i: int(i['initiative']), reverse=True)
        if self.inInit:
            if self.inInit and tmp != self.initiativeList[self.initiativeCount]["charName"]:
                self.initiativeCount += 1

    def number_units(self):
        for x in range(len(self.unitList)):
            self.unitList[x]["unitNum"] = x

    def insert_initiative(self, creature):
        if not creature["initiative"]: return
        if len(self.initiativeList) == 0:
            self.initiativeList.insert(0, creature)
            return
        for x in range(len(self.initiativeList)):
            if int(self.initiativeList[x]["initiative"]) <= int(creature["initiative"]):
                self.initiativeList.insert(x, creature)
                return
        self.initiativeList.append(creature)

    def player_json(self):
        playerObject = {
            "unitList": [],
            "room": self.room,
            "name": self.name,
            "inInit": self.inInit,
            "initiativeCount": self.initiativeCount,
            "roundCount": self.roundCount,
            "playerList": self.playerList,
            "mapArray": self.mapArray,
            "movePath": self.movePath
        }  # add visible units from unitlist
        if self.inInit:
            playerObject["initiativeList"] = self.initiativeList
        else:
            playerObject["initiativeList"] = []
        tmpMapArray = []
        for i in range(len(self.unitList)):
            if self.unitList[i]["controlledBy"] != "gm" or (
                    "x" in self.unitList[i].keys() and self.mapArray[self.unitList[i]["x"]][self.unitList[i]["y"]][
                "seen"]):
                playerObject["unitList"].append(self.unitList[i])
        for y in range(len(self.mapArray)):
            tmpMapLine = []
            for x in range(len(self.mapArray[y])):
                tmpMapLine.append({"tile": self.mapArray[y][x]["tile"]})
                if self.mapArray[y][x]["secret"]:
                    tmpMapLine[x] = {"tile": "wallTile"}
                if not self.mapArray[y][x]["seen"]:
                    tmpMapLine[x] = {"tile": "unseenTile"}
            tmpMapArray.append(tmpMapLine)
        playerObject["mapArray"] = tmpMapArray
        return playerObject

    def calc_path(self, tmpUnit, end, moveType):
        maxMove = 6
        if "movementSpeed" not in tmpUnit.keys():
            tmpUnit["movementSpeed"] = 30
        else:
            tmpUnit["movementSpeed"] = int(tmpUnit["movementSpeed"])
        if moveType == 0:
            maxMove = 1
        elif moveType == 1:
            maxMove = tmpUnit["movementSpeed"] / 5
        elif moveType == 2:
            maxMove = tmpUnit["movementSpeed"] * 2 / 5
        elif moveType == 3:
            maxMove = -1
        else:
            tmpUnit["x"] = end[0]
            tmpUnit["y"] = end[1]
            return
        if "hasted" in tmpUnit.keys() and tmpUnit["hasted"] and not moveType == 0:
            maxMove = min(maxMove * 2, maxMove + 6)
        maxMove -= tmpUnit["distance"]
        # print((tmpUnit["x"], tmpUnit["y"]))
        path = astar(self.mapArray, (tmpUnit["x"], tmpUnit["y"]), end, maxMove)
        tmpUnit["distance"] += path.pop(0)
        for x in path:
            tmpUnit["movePath"].append(x)
        tmpUnit["x"] = path[-1][0]
        tmpUnit["y"] = path[-1][1]
        return

    def reveal_map(self, selectedPlayer):
        if not "x" in self.unitList[selectedPlayer].keys(): return
        x = self.unitList[selectedPlayer]["x"]
        y = self.unitList[selectedPlayer]["y"]
        for xBox in range(-10, 11):
            for yBox in range(-10, 11):
                cells = raytrace(x, y, max(0, x + xBox), max(0, y + yBox))
                for distance in range(len(cells)):
                    try:
                        self.mapArray[cells[distance][0]][cells[distance][1]]["seen"] = True
                        if not self.mapArray[cells[distance][0]][cells[distance][1]]["walkable"]:
                            break
                    except:
                        break


def raytrace(x0, y0, x1, y1):  # https://playtechs.blogspot.com/2007/03/raytracing-on-grid.html
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
        cells.append([x, y])
        if error > 0:
            x += x_inc
            error -= dy
        else:
            y += y_inc
            error += dx
    return cells


def astar(maze, start, end, maxMove):
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

    # print(start)
    # print(end)
    # print(len(maze))
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
            print(current.g)
            totalDistance = 0
            while current is not None:
                print(current.position)
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
                    len(maze[len(maze) - 1]) - 1) or node_position[1] < 0:
                continue

            # test diagonal step
            if new_position[0] != 0 and new_position[1] != 0:
                if not maze[current_node.position[0]][node_position[1]]["walkable"] or not \
                        maze[node_position[0]][current_node.position[1]]["walkable"]:
                    continue

            # Make sure walkable terrain
            if not maze[node_position[0]][node_position[1]]["walkable"] \
                    or not maze[node_position[0]][node_position[1]]["seen"]:
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
