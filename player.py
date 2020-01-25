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

    def to_json(self):
        tmp_json = super(Player, self).to_json()
        tmp_json["connected"] = self.connected
        tmp_json["connections"] = self.connections
        tmp_json["requestInit"] = self.requestInit
        tmp_json["type"] = self.type
        tmp_json["revealsMap"] = self.revealsMap
        tmp_json["controlledBy"] = self.controlledBy
        tmp_json["sid"] = self.sid
        tmp_json["inventories"] = self.inventories
        return tmp_json