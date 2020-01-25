class Unit(object):
    def __init__(self, unitdict):
        self.charName = unitdict["charName"]
        self.size = default(unitdict, "size", "medium")
        self.x = default(unitdict, "x", -1)
        self.y = default(unitdict, "y", -1)
        self.location = default(unitdict, "location", [self.x, self.y])
        self.occupied_tiles = []
        self.inInit = default(unitdict, "inInit", False)
        self.unitNum = default(unitdict, "unitNum", -1)
        self.controlledBy = default(unitdict, "controlledBy", "")
        self.charShortName = default(unitdict, "charShortName", "")
        self.color = default(unitdict, "color", "black")
        self.HP = default(unitdict, "HP", "0")
        self.maxHP = default(unitdict, "maxHP", "0")
        self.type = default(unitdict, "type", "mob")
        self.HD = default(unitdict, "HD", 1)
        self.initiative = default(unitdict, "initiative", 0)
        self.revealsMap = default(unitdict, "revealsMap", False)
        self.perception = default(unitdict, "perception", 0)
        self.movementSpeed = default(unitdict, "movementSpeed", 30)
        self.dex = default(unitdict, "dex", 10)
        self.token = default(unitdict, "token", "")
        self.hasted = default(unitdict, "hasted", False)
        self.distance = default(unitdict, "distance", 0) #distance traveled already
        self.movePath = default(unitdict, "movePath", 0)
        if self.location != [-1, -1] and self.occupied_tiles == []:
            self.occupied_tiles.append(self.location)
            if self.size == "large":
                self.occupied_tiles.append(self.location + [-1, 0])
                self.occupied_tiles.append(self.location + [0, +1])
                self.occupied_tiles.append(self.location + [-1, +1])



    def to_json(self):
        return {
            "charName": self.charName,
            "size": self.size,
            "location": self.location,
            "occupied_tiles": self.occupied_tiles,
            "inInit": self.inInit,
            "unitNum": self.unitNum,
            "controlledBy": self.controlledBy,
            "charShortName": self.charShortName,
            "color": self.color,
            "HP": self.HP,
            "maxHP": self.maxHP,
            "type": self.type,
            "HD": self.HD,
            "initiative": self.initiative,
            "revealsMap": self.revealsMap,
            "perception": self.perception,
            "movementSpeed": self.movementSpeed,
            "dex": self.dex,
            "token": self.token,
            "hasted": self.hasted,
            "distance": self.distance,
            "movePath": self.movePath,
            "x": self.x,
            "y": self.y
        }

def default(dict, key, default):
    if key in dict:
        return dict[key]
    else:
        return default