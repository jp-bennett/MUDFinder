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
        self.inventories = {}
        if "inventories" in unitdict:
            self.inventories = unitdict["inventories"]
        else:
            self.inventories = {}
            self.inventories[self.charName] = {}
            self.inventories[self.charName]["gp"] = []
            self.inventories[self.charName]["Inventory"] = []