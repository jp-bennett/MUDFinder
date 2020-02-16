class Unit(object):
    def __init__(self, unitdict):
        self.charName = unitdict["charName"]
        self.alignment = default(unitdict, "alignment", "N")
        self.size = default(unitdict, "size", "medium")
        self.x = default(unitdict, "x", -1)
        self.y = default(unitdict, "y", -1)
        self.location = default(unitdict, "location", [self.x, self.y])
        self.occupied_tiles = []
        self.inInit = default(unitdict, "inInit", False)
        self.hasted = default(unitdict, "hasted", False)
        self.unitNum = default(unitdict, "unitNum", -1)
        self.initNum = default(unitdict, "initNum", -1)
        self.controlledBy = default(unitdict, "controlledBy", "")
        self.charShortName = default(unitdict, "charShortName", "")
        self.color = default(unitdict, "color", "black")
        self.HP = default(unitdict, "HP", "")
        self.maxHP = default(unitdict, "maxHP", "")
        self.DR = default(unitdict, "DR", "")
        self.wounds = default(unitdict, "wounds", "")
        self.nonLethal = default(unitdict, "nonLethal", "")
        self.type = default(unitdict, "type", "mob")
        self.HD = default(unitdict, "HD", 1)
        self.initiative = default(unitdict, "initiative", 0)
        self.revealsMap = default(unitdict, "revealsMap", False)
        self.perception = default(unitdict, "perception", 0)
        self.movementSpeed = default(unitdict, "movementSpeed", 30)
        self.flySpeed = default(unitdict, "flySpeed", "")
        self.flyManeuverability = default(unitdict, "flyManeuverability", "")
        self.swimSpeed = default(unitdict, "swimSpeed", "")
        self.climbSpeed = default(unitdict, "climbSpeed", "")
        self.burrowSpeed = default(unitdict, "burrowSpeed", "")
        self.token = default(unitdict, "token", "")
        self.hasted = default(unitdict, "hasted", False)
        self.distance = default(unitdict, "distance", 0)  # distance traveled already
        self.movePath = default(unitdict, "movePath", 0)
        self.skills = default(unitdict, "skills", [])

        # ability scores:
        self.STR = default(unitdict, "STR", "")
        self.DEX = default(unitdict, "DEX", "")
        self.CON = default(unitdict, "CON", "")
        self.INT = default(unitdict, "INT", "")
        self.WIS = default(unitdict, "WIS", "")
        self.CHA = default(unitdict, "CHA", "")
        self.ACArmor = default(unitdict, "ACArmor", "")
        self.ACShield = default(unitdict, "ACShield", "")
        self.ACNatural = default(unitdict, "ACNatural", "")
        self.ACMisc = default(unitdict, "ACMisc", "")
        self.deflection = default(unitdict, "deflection", "")

        self.BAB = default(unitdict, "BAB", "")
        self.SR = default(unitdict, "SR", "")
        self.ER = default(unitdict, "ER", "")
        self.weapons = default(unitdict, "weapons", [])
        self.spellcasting = default(unitdict, "spellcasting", [])

        if self.location != [-1, -1] and self.occupied_tiles == []:
            self.occupied_tiles.append(self.location)
            if self.size == "large":
                self.occupied_tiles.append(self.location + [-1, 0])
                self.occupied_tiles.append(self.location + [0, +1])
                self.occupied_tiles.append(self.location + [-1, +1])

    def to_json(self):
        return {
            "charName": self.charName,
            "alignment": self.alignment,
            "size": self.size,
            "location": self.location,
            "occupied_tiles": self.occupied_tiles,
            "inInit": self.inInit,
            "unitNum": self.unitNum,
            "initNum": self.initNum,
            "controlledBy": self.controlledBy,
            "charShortName": self.charShortName,
            "color": self.color,
            "HP": self.HP,
            "maxHP": self.maxHP,
            "DR": self.DR,
            "wounds": self.wounds,
            "nonLethal": self.nonLethal,
            "type": self.type,
            "HD": self.HD,
            "initiative": self.initiative,
            "revealsMap": self.revealsMap,
            "perception": self.perception,
            "movementSpeed": self.movementSpeed,
            "flySpeed": self.flySpeed,
            "flyManeuverability": self.flyManeuverability,
            "swimSpeed": self.swimSpeed,
            "climbSpeed": self.climbSpeed,
            "burrowSpeed": self.burrowSpeed,
            "token": self.token,
            "hasted": self.hasted,
            "distance": self.distance,
            "movePath": self.movePath,
            "x": self.x,
            "y": self.y,
            "skills": self.skills,
            "STR": self.STR,
            "DEX": self.DEX,
            "CON": self.CON,
            "INT": self.INT,
            "WIS": self.WIS,
            "CHA": self.CHA,
            "ACArmor": self.ACArmor,
            "ACShield": self.ACShield,
            "ACNatural": self.ACNatural,
            "ACMisc": self.ACMisc,
            "deflection": self.deflection,
            "BAB": self.BAB,
            "SR": self.SR,
            "ER": self.ER,
            "weapons": self.weapons,
            "spellcasting": self.spellcasting
        }


def default(local_dict, key, local_default):
    if key in local_dict:
        return local_dict[key]
    else:
        return local_default
