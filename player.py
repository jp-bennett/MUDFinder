from unit import Unit, default


class Player(Unit):
    def __init__(self, unitdict):
        super(Player, self).__init__(unitdict)
        self.connected = False
        self.connections = 0
        self.requestInit = False
        self.type = default(unitdict, "type", "player")
        self.revealsMap = True
        self.controlledBy = self.charName
        self.sid = ""
        self.height = default(unitdict, "height", "")
        self.weight = default(unitdict, "weight", "")
        self.level = default(unitdict, "level", "")
        self.age = default(unitdict, "age", "")
        self.deity = default(unitdict, "deity", "")
        self.hair = default(unitdict, "hair", "")
        self.eyes = default(unitdict, "eyes", "")
        self.race = default(unitdict, "race", "")
        self.gender = default(unitdict, "gender", "")
        self.homeland = default(unitdict, "homeland", "")
        self.armorSpeed = default(unitdict, "armorSpeed", "")
        self.miscToInit = default(unitdict, "miscToInit", "")
        self.fortBase = default(unitdict, "fortBase", "")
        self.fortMagic = default(unitdict, "fortMagic", "")
        self.fortMisc = default(unitdict, "fortMisc", "")
        self.reflexBase = default(unitdict, "reflexBase", "")
        self.reflexMagic = default(unitdict, "reflexMagic", "")
        self.reflexMisc = default(unitdict, "reflexMisc", "")
        self.willBase = default(unitdict, "willBase", "")
        self.willMagic = default(unitdict, "willMagic", "")
        self.willMisc = default(unitdict, "willMisc", "")

        self.image = default(unitdict, "image", "")
        #self.inventories = {}
        if "inventories" in unitdict:
            self.inventories = unitdict["inventories"]
        else:
            self.inventories = {}
            self.inventories[self.charName] = {}
            self.inventories[self.charName]["gp"] = []
            self.inventories[self.charName]["inventory"] = []

    def to_json(self):
        tmp_json = super(Player, self).to_json()
        tmp_json["connected"] = self.connected
        tmp_json["connections"] = self.connections
        tmp_json["requestInit"] = self.requestInit
        tmp_json["type"] = self.type
        tmp_json["revealsMap"] = self.revealsMap
        tmp_json["controlledBy"] = self.controlledBy
        tmp_json["sid"] = self.sid
        tmp_json["height"] = self.height
        tmp_json["weight"] = self.weight
        tmp_json["inventories"] = self.inventories
        tmp_json["level"] = self.level
        tmp_json["age"] = self.age
        tmp_json["deity"] = self.deity
        tmp_json["hair"] = self.hair
        tmp_json["eyes"] = self.eyes
        tmp_json["race"] = self.race
        tmp_json["gender"] = self.gender
        tmp_json["homeland"] = self.homeland
        tmp_json["armorSpeed"] = self.armorSpeed
        tmp_json["miscToInit"] = self.miscToInit
        tmp_json["fortBase"] = self.fortBase
        tmp_json["fortMagic"] = self.fortMagic
        tmp_json["fortMisc"] = self.fortMisc
        tmp_json["reflexBase"] = self.reflexBase
        tmp_json["reflexMagic"] = self.reflexMagic
        tmp_json["reflexMisc"] = self.reflexMisc
        tmp_json["willBase"] = self.willBase
        tmp_json["willMagic"] = self.willMagic
        tmp_json["willMisc"] = self.willMisc
        tmp_json["image"] = self.image
        return tmp_json