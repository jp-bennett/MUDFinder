import copy
import json
import time
import io
import base64
import sqlite3
import uuid
import atexit
from os import path
from os import mkdir
from threading import Lock
from random import randint

from flask import Flask, render_template, request, redirect
from flask_socketio import SocketIO, join_room, emit

from session import Session

from player import Player
from unit import Unit
global savegame_lock
savegame_lock = Lock()


def roll_dice(input_roll_string):
    roll_output = ""
    roll_type = ""
    show_totals: bool = False
    first_time: bool = True
    if '"' in input_roll_string:
        partial_roll_string = input_roll_string[input_roll_string.find('"') + 1:]
        roll_type = partial_roll_string[:partial_roll_string.find('"')]
        input_roll_string = input_roll_string.replace('"' + roll_type + '"', "")
    if '!' in input_roll_string:
        show_totals = True
    for subRollString in input_roll_string.split(","):
        roll_total = 0
        totals = ""
        roll_string = "".join(filter(lambda x: x in "0123456789d+-*/÷×xX",
                                     subRollString))
        # silly filter objects. .join gives us a string. Also, slice off the leading /
        if not roll_string[:1] in "+-*/÷×xX":
            roll_string = "+" + roll_string
        roll_string_locations = [i for i, char in enumerate(roll_string) if char in "+-*/÷×xX"]
        for position in range(len(roll_string_locations)):
            if position + 1 < len(roll_string_locations):
                partial_roll_string = roll_string[roll_string_locations[position]:roll_string_locations[position + 1]]
            else:
                partial_roll_string = (roll_string[roll_string_locations[position]:])
            if "d" in partial_roll_string:
                partial_roll_value = 0
                roll_count_txt = partial_roll_string[1:partial_roll_string.find("d")]
                if len(roll_count_txt) > 0:
                    roll_count = int(roll_count_txt)
                else:
                    roll_count = 1
                roll_die = int(partial_roll_string[partial_roll_string.find("d") + 1:])
                for i in range(roll_count):
                    single_roll_value = randint(1, roll_die)
                    partial_roll_value += single_roll_value
                    totals += partial_roll_string[:1] + str(single_roll_value)
                partial_roll_string = partial_roll_string[:1] + str(partial_roll_value)
            else:
                totals += partial_roll_string
            if partial_roll_string[:1] in "+":
                roll_total += int(partial_roll_string[1:])
            if partial_roll_string[:1] in "-":
                roll_total -= int(partial_roll_string[1:])
            if partial_roll_string[:1] in "/÷":
                roll_total /= int(partial_roll_string[1:])
            if partial_roll_string[:1] in "*×xX":
                roll_total *= int(partial_roll_string[1:])
        if not first_time:
            roll_output += ", "
        first_time = False
        if show_totals:
            roll_output += totals + "=" + str(roll_total)
        else:
            roll_output += str(roll_total)
    return str(roll_output) + " " + roll_type


# initialize Flask
app = Flask(__name__)
socketio = SocketIO(app, async_mode="eventlet", cors_allowed_origins="*")
ROOMS = {}  # dict to track active rooms
thread = None
thread_lock = Lock()
if not path.exists("saves"):
    mkdir("saves")


def savegame_thread():
    global savegame_lock
    global ROOMS
    with app.app_context():
        while True:
            socketio.sleep(300)
            with thread_lock:
                for room in ROOMS.keys():
                    with open("saves/" + room + ".json", "w") as outfile:
                        json.dump(ROOMS[room].gen_save(), outfile)


# https://stackoverflow.com/questions/14384739/how-can-i-add-a-background-thread-to-flask
# https://github.com/miguelgrinberg/Flask-SocketIO/issues/651 https://github.com/miguelgrinberg/Flask-SocketIO/issues/651


def check_room(room):
    global ROOMS
    if room in ROOMS:
        return True
    elif path.exists("saves/" + room + ".json"):
        with open("saves/" + room + ".json", "r") as infile:
            data = json.loads(infile.read())
            ROOMS[room] = Session(room, data["gmKey"], data["name"])
            ROOMS[room].from_json(data)
            # versioning
            for x in ROOMS[room].unitList:
                if x.token[0:18] == "data:image;base64,":
                    image_uuid = str(uuid.uuid4())
                    ROOMS[room].images[image_uuid] = x.token[19:]
                    x.token = "get_image.html?room=" + room + "&id=" + image_uuid
                if x.type == "player" and x.image[0:18] == "data:image;base64,":
                    image_uuid = str(uuid.uuid4())
                    ROOMS[room].images[image_uuid] = x.image[19:]
                    x.image = "get_image.html?room=" + room + "&id=" + image_uuid
            ROOMS[room].number_units()
            return True
    else:
        return False


@app.route('/')
def index():
    """Serve the index HTML"""
    return render_template('index.html')


@app.route('/functions.js')
def functions_js():
    return render_template('functions.js')


@app.route('/mudfinder.css')
def css():
    return render_template('mudfinder.css')


@app.route('/player.html')
def player_page():
    return render_template('player.html', current_time=int(time.time()))


@app.route('/spectator.html')
def spectator_page():
    return render_template('spectator.html', current_time=int(time.time()))


@app.route('/gm.html')
def gm_page():
    # look up room ID and check GM id.
    """gm view"""
    return render_template('gm.html', current_time=int(time.time()))


@app.route('/upload.html', methods=['GET', 'POST'])
def upload():
    f = request.files['file']
    data = json.loads(f.read())
    room = data["room"]
    ROOMS[room] = Session(room, data["gmKey"], data["name"])
    ROOMS[room].from_json(data)
    ROOMS[room].number_units()
    return redirect("gm.html?gmKey=" + ROOMS[room].gmKey + "&room=" + room)


@app.route('/download.html')
def save_download():
    room = request.args['room']
    if check_room(room) and ROOMS[room].gmKey == request.args['gmKey']:
        response = app.response_class(
            response=json.dumps(ROOMS[room].gen_save()),
            status=200,
            headers={"Content-disposition":
                     "attachment; filename=" + ROOMS[room].name + ".json"},
            mimetype='application/json'
        )
        return response


@app.route('/get_image.html')
def get_image():
    room = request.args['room']
    if check_room(room):
        response = app.response_class(
            response=base64.b64decode(ROOMS[room].images[request.args['id']]),
            status=200,
            mimetype='image'
        )
        return response


@socketio.on('lore_upload')
def on_lore_upload(room, lore_size, lore_name, lore_text, lore_owner):
    if check_room(room):
        loreNum = len(ROOMS[room].lore)
        ROOMS[room].lore.append(
            {"loreSize": lore_size, "loreName": lore_name, "loreText": lore_text, "loreVisible": False,
             "loreOwner": lore_owner}
        )
        ROOMS[room].loreFiles[loreNum] = io.BytesIO()
        return loreNum


@socketio.on('write_chunk')
def write_chunk(room, loreNum, offset, data):
    if check_room(room):
        ROOMS[room].loreFiles[loreNum].seek(offset)
        ROOMS[room].loreFiles[loreNum].write(data)
        if offset + len(data) >= ROOMS[room].lore[loreNum]["loreSize"]:
            ROOMS[room].loreFiles[loreNum] = base64.b64encode(ROOMS[room].loreFiles[loreNum].getvalue()).decode()


@socketio.on('get_lore_file')
def get_lore_file(room, loreNum):
    if check_room(room):
        return ROOMS[room].loreFiles[loreNum]


@socketio.on('lore_url')
def on_lore_url(room, lore_url, lore_name, lore_text, lore_owner):
    if check_room(room):
        ROOMS[room].lore.append(
            {"loreURL": lore_url, "loreName": lore_name, "loreText": lore_text, "loreVisible": False, "loreSize": 0,
             "loreOwner": lore_owner})
        emit("showLore", {"lore": ROOMS[room].lore, "lore_num": None}, room=room)


@socketio.on('image_upload')
def on_image_upload(room, image, title, owner):
    if check_room(room):
        if image[0:18] == "data:image;base64,":
            image_uuid = str(uuid.uuid4())
            ROOMS[room].images[image_uuid] = image[19:]
            image = "get_image.html?room=" + room + "&id=" + image_uuid
        if title == "charImage":
            ROOMS[room].playerList[owner].image = image
        if title == "charToken":
            ROOMS[room].playerList[owner].token = image
        if title == "unitToken":
            ROOMS[room].unitList[int(owner)].token = image
        if title == "loreImage":
            return image
        emit('do_update', ROOMS[room].player_json(), room=room)


@socketio.on('lore_visible')
def on_lore_visible(room, gmKey, lore_num):  # but player can choose. TODO:
    if check_room(room) and (ROOMS[room].gmKey == gmKey or gmKey == ROOMS[room].lore[lore_num]["loreOwner"]):
        ROOMS[room].lore[lore_num]["loreVisible"] = not ROOMS[room].lore[lore_num]["loreVisible"]
        if not ROOMS[room].lore[lore_num]["loreVisible"]:
            lore_num = None
        emit("showLore", {"lore": ROOMS[room].lore, "lore_num": lore_num}, room=room)


@socketio.on('delete_lore')
def on_delete_lore(room, gmKey, lore_num):
    if check_room(room) and (ROOMS[room].gmKey == gmKey or gmKey == ROOMS[room].lore[lore_num]["loreOwner"]):
        ROOMS[room].lore.pop(lore_num)
        tmp_keys = {}
        for x in ROOMS[room].loreFiles.keys():
            if x > lore_num:
                tmp_keys[x - 1] = ROOMS[room].loreFiles[x]
            elif x < lore_num:
                tmp_keys[x] = ROOMS[room].loreFiles[x]
        ROOMS[room].loreFiles = tmp_keys
        emit("reloadLore", {"lore": ROOMS[room].lore, "lore_num": None}, room=room)


@socketio.on('get_lore')
def on_get_lore(room):
    if check_room(room):
        emit("showLore", {"lore": ROOMS[room].lore, "lore_num": None})


@socketio.on('player_join')
def on_player_join(data):
    room = data['room']
    if check_room(room):
        join_room(room)
        if not any(d == data['charName'] for d in ROOMS[room].playerList):  # TODO: make this a class function
            ROOMS[room].playerList[data['charName']] = Player(data)
            ROOMS[room].unitList.append(ROOMS[room].playerList[data['charName']])
        ROOMS[room].playerList[data['charName']].sid = request.sid
        ROOMS[room].playerList[data['charName']].connections += 1
        ROOMS[room].playerList[data['charName']].connected = True
        ROOMS[room].number_units()
        emit('draw_map', ROOMS[room].player_map())
        emit('do_update', ROOMS[room].player_json(), room=room)
    else:
        emit('error', {'error': 'Unable to join room. Room does not exist.'})


@socketio.on('spectator_join')
def on_spectator_join(data):
    """Join a game lobby"""
    room = data['room']
    if check_room(room):
        join_room(room)
        emit('draw_map', ROOMS[room].player_map())
        emit('do_update', ROOMS[room].player_json(), room=room)
    else:
        emit('error', {'error': 'Unable to join room. Room does not exist.'})


@socketio.on('gm_update')
def on_gm_update(data):
    """gm session update"""
    room = data['room']
    if check_room(room) and ROOMS[room].gmKey == data['gmKey']:
        emit('gm_update', ROOMS[room].to_json())


@socketio.on('join_gm')
def on_join_gm(data):
    """Join a game as GM"""
    room = data['room']
    if check_room(room) and ROOMS[room].gmKey == data['gmKey']:
        if ROOMS[room].gmRoom == "":
            ROOMS[room].gmRoom = request.sid
        join_room(ROOMS[room].gmRoom)
        emit('gm_map', ROOMS[room].mapArray)
        emit('gm_update', ROOMS[room].to_json())
    else:
        emit('error', {'error': 'Unable to join room. Room does not exist.'})


@socketio.on('request_init')
def on_request_init(data):
    """request initiative"""
    room = data['room']
    if check_room(room) and ROOMS[room].gmKey == data['gmKey']:
        for d in ROOMS[room].playerList:
            ROOMS[room].playerList[d].requestInit = True
        ROOMS[room].send_updates()


@socketio.on('send_initiative')
def on_initiative(data):
    """recieve initiative"""
    room = data['room']
    if check_room(room):
        ROOMS[room].playerList[data['charName']].requestInit = False
        for x in ROOMS[room].unitList:
            if x.controlledBy == data['charName'] and ("inInit" not in data or not x.inInit):
                tmpInit = data["initiative"].pop(0)
                if tmpInit != "":
                    x.initiative = tmpInit
                    x.inInit = True
                    x.flatFooted = True
                    x.movePath = []
                    x.distance = 0
                    ROOMS[room].insert_initiative(x)
        ROOMS[room].send_updates()


@socketio.on('begin_init')
def on_begin_init(data):
    """begin initiative"""
    room = data['room']
    if check_room(room) and ROOMS[room].gmKey == data['gmKey']:
        ROOMS[room].inInit = True
        ROOMS[room].initiativeCount = 0
        ROOMS[room].roundCount = 1
        ROOMS[room].send_updates()


@socketio.on('advance_init')
def on_advance_init(data):
    room = data['room']
    if check_room(room):
        if ("gmKey" in data and ROOMS[room].gmKey == data['gmKey']) or \
                ROOMS[room].initiativeList[ROOMS[room].initiativeCount].controlledBy == data["charName"]:
            ROOMS[room].initiativeCount += 1
            for effect in ROOMS[room].effects:
                if effect["duration"] == "instantaneous":
                    ROOMS[room].effects.remove(effect)
            if ROOMS[room].initiativeCount >= len(ROOMS[room].initiativeList):
                ROOMS[room].initiativeCount = 0
                ROOMS[room].roundCount += 1
            ROOMS[room].initiativeList[ROOMS[room].initiativeCount].flatFooted = False
            ROOMS[room].initiativeList[ROOMS[room].initiativeCount].movePath = []
            ROOMS[room].initiativeList[ROOMS[room].initiativeCount].distance = 0
            ROOMS[room].send_updates()


@socketio.on('end_init')
def on_end_init(data):
    room = data['room']
    if check_room(room) and ROOMS[room].gmKey == data['gmKey']:
        ROOMS[room].inInit = False
        for x in ROOMS[room].unitList:
            x.inInit = False
            x.initNum = -1
            x.movePath = []
            x.distance = 0
            if x.type == "player":
                x.initiative = ""
        ROOMS[room].initiativeCount = 0
        ROOMS[room].initiativeList = []
        ROOMS[room].send_updates()


@socketio.on('save_encounter')
def on_save_encounter(data):
    room = data['room']
    if check_room(room) and ROOMS[room].gmKey == data['gmKey']:
        ROOMS[room].savedEncounters[data['encounterName']] = {}
        ROOMS[room].savedEncounters[data['encounterName']]["mapArray"] = copy.deepcopy(ROOMS[room].mapArray)
        ROOMS[room].savedEncounters[data['encounterName']]["unitList"] = []
        for x in ROOMS[room].unitList:
            if x.controlledBy == "gm":
                ROOMS[room].savedEncounters[data['encounterName']]["unitList"].append(x.to_json())
        ROOMS[room].send_updates()


@socketio.on('remove_encounter')
def on_remove_encounter(data):
    room = data['room']
    if check_room(room) and ROOMS[room].gmKey == data['gmKey']:
        ROOMS[room].savedEncounters.pop(data['encounterName'])
        ROOMS[room].send_updates()


@socketio.on('load_encounter')
def on_load_encounter(data):
    room = data['room']
    if check_room(room) and ROOMS[room].gmKey == data['gmKey']:
        ROOMS[room].mapArray = copy.deepcopy(ROOMS[room].savedEncounters[data['encounterName']]["mapArray"])
        for x in reversed(ROOMS[room].unitList):
            if x.controlledBy == "gm":
                ROOMS[room].unitList.remove(x)
            else:
                if data["clearLocations"]:
                    x.x = -1
                    x.y = -1
                    x.location = [-1, -1]
        for x in ROOMS[room].savedEncounters[data['encounterName']]["unitList"]:
            ROOMS[room].unitList.append(Unit(copy.deepcopy(x)))
        ROOMS[room].number_units()
        if not ROOMS[room].mapArray[0][0]["x"]:
            for y in range(len(ROOMS[room].mapArray)):
                for x in range(len(ROOMS[room].mapArray[y])):
                    ROOMS[room].mapArray[y][x]["x"] = x
                    ROOMS[room].mapArray[y][x]["y"] = y
        emit('gm_map', ROOMS[room].mapArray)
        emit('draw_map', ROOMS[room].player_map(), room=room)
        ROOMS[room].send_updates()


@socketio.on('add_player_unit')
def on_add_player_unit(data):
    room = data['room']
    if check_room(room):
        unit = Unit(data['unit'])
        unit.controlledBy = data["charName"]
        if ROOMS[room].inInit:
            unit.initiative = ROOMS[room].playerList[data["charName"]].initiative
        ROOMS[room].unitList.append(unit)
        ROOMS[room].number_units()
        ROOMS[room].send_updates()


@socketio.on('clear_map')
def on_clear_map(data):
    room = data['room']
    if check_room(room) and ROOMS[room].gmKey == data['gmKey']:
        ROOMS[room].mapArray = []
        ROOMS[room].inInit = False
        for x in reversed(ROOMS[room].unitList):  # since we're removing elements, have to walk it backwards
            if x.controlledBy == "gm":
                ROOMS[room].unitList.remove(x)
            else:
                x.inInit = False
                if data["clearLocations"]:
                    x.x = -1
                    x.y = -1
                    x.location = [-1, -1]
        ROOMS[room].initiativeCount = 0
        ROOMS[room].initiativeList = []
        ROOMS[room].number_units()
        emit('gm_map', ROOMS[room].mapArray)
        emit('draw_map', ROOMS[room].player_map(), room=room)
        ROOMS[room].send_updates()


@socketio.on('add_unit')
def on_add_unit(data):
    room = data['room']
    if check_room(room):
        if "gmKey" in data.keys() and ROOMS[room].gmKey == data['gmKey']:
            unit = Unit(data['unit'])
            ROOMS[room].unitList.append(unit)
            if data["addToInitiative"]:
                ROOMS[room].insert_initiative(ROOMS[room].unitList[-1])
                ROOMS[room].unitList[-1].inInit = True
                ROOMS[room].unitList[-1].flatFooted = True
            ROOMS[room].number_units()
            ROOMS[room].send_updates()
        else:
            unit = Unit(data['unit'])
            if ROOMS[room].inInit:
                unit.initiative = ROOMS[room].playerList[data["charName"]].initiative
            ROOMS[room].unitList.append(unit)
            ROOMS[room].number_units()
            ROOMS[room].send_updates()


@socketio.on('update_unit')
def on_update_unit(data):
    room = data['room']
    if check_room(room):
        tmp_unit = ROOMS[room].unitList[int(data["unitNum"])]
        tmp_unit.charShortName = data["charShortName"]
        # tmp_unit.token = data["token"]
        tmp_unit.color = data["color"]
        tmp_unit.perception = data["perception"]
        tmp_unit.movementSpeed = data["movementSpeed"]
        tmp_unit.DEX = data["DEX"]
        tmp_unit.size = data["size"]
        tmp_unit.darkvision = data["darkvision"]
        tmp_unit.lowLight = data["lowLight"]
        tmp_unit.trapfinding = data["trapfinding"]
        # tmp_unit.hasted = data["hasted"]
        tmp_unit.permanentAbilities = data["permanentAbilities"]
        if "gmKey" in data.keys() and ROOMS[room].gmKey == data['gmKey']:
            tmp_unit.revealsMap = data["revealsMap"]
            tmp_unit.initiative = data["initiative"]
        ROOMS[room].send_updates()


@socketio.on('remove_unit_location')
def on_remove_unit_location(room, gmKey, tmp_unitNum):
    if check_room(room):
        if ROOMS[room].gmKey == gmKey:
            tmp_unit = ROOMS[room].unitList[int(tmp_unitNum)]
            tmp_unit.x = -1
            tmp_unit.y = -1
            ROOMS[room].send_updates()


@socketio.on('add_player_spellcasting')
def on_add_player_spellcasting(data):
    room = data['room']
    if check_room(room):
        tmp_unit = ROOMS[room].playerList[data["charName"]]
        tmp_spell = {}
        tmp_spell["class"] = data["class"]
        tmp_spell["classLevel"] = data["level"]
        tmp_spell["casterLevel"] = data["level"]
        tmp_spell["castingStat"] = "INT"
        if tmp_spell["class"] in ["Arcanist", "Wizard", "Alchemist", "Magus", "Witch"]:
            tmp_spell['hasSpellbook'] = True
            tmp_spell["spellbook"] = []
        else:
            tmp_spell['hasSpellbook'] = False
        if tmp_spell["class"] in ["Arcanist", "Magus", "Gifted Blade"]:
            tmp_spell['hasPoints'] = True
            tmp_spell['currentPoints'] = 0
            tmp_spell['maxPoints'] = 0
            tmp_spell['dailyPoints'] = 0
        else:
            tmp_spell['hasPoints'] = False
        if tmp_spell["class"] in ["Arcanist", "Sorcerer", "Alchemist"]:
            tmp_spell["hasSpellSlots"] = True
            tmp_spell["spellSlots1"] = 0
            tmp_spell["spellSlots2"] = 0
            tmp_spell["spellSlots3"] = 0
            tmp_spell["spellSlots4"] = 0
            tmp_spell["spellSlots5"] = 0
            tmp_spell["spellSlots6"] = 0
            tmp_spell["spellSlots7"] = 0
            tmp_spell["spellSlots8"] = 0
            tmp_spell["spellSlots9"] = 0
            tmp_spell["spellSlotsDaily1"] = 0
            tmp_spell["spellSlotsDaily2"] = 0
            tmp_spell["spellSlotsDaily3"] = 0
            tmp_spell["spellSlotsDaily4"] = 0
            tmp_spell["spellSlotsDaily5"] = 0
            tmp_spell["spellSlotsDaily6"] = 0
            tmp_spell["spellSlotsDaily7"] = 0
            tmp_spell["spellSlotsDaily8"] = 0
            tmp_spell["spellSlotsDaily9"] = 0
        else:
            tmp_spell["hasSpellSlots"] = False
        if tmp_spell["class"] in ["Arcanist", "Magus", "Gifted Blade", "Wizard", "Witch", "Cleric"]:
            tmp_spell["preparesSpells"] = True
            tmp_spell["preparedSpells"] = [[], [], [], [], [], [], [], [], [], []]
            tmp_spell["preparedSpellsDaily"] = [{"number": 0, "spells": []}, {"number": 0, "spells": []}, {"number": 0, "spells": []},
                                                {"number": 0, "spells": []}, {"number": 0, "spells": []}, {"number": 0, "spells": []},
                                                {"number": 0, "spells": []}, {"number": 0, "spells": []}, {"number": 0, "spells": []}, {"number": 0, "spells": []}]
            if tmp_spell["class"] in ["Magus", "Wizard", "Witch", "Cleric"]:
                tmp_spell["Vancian"] = True
            else:
                tmp_spell["Vancian"] = False
        tmp_unit.spellcasting.append(tmp_spell)
        ROOMS[room].send_updates()


@socketio.on('update_player')
def on_update_player(data):
    room = data['room']
    if check_room(room):
        tmp_unit = ROOMS[room].playerList[data["charName"]]
        tmp_unit.alignment = data["alignment"]
        tmp_unit.size = data["size"]
        tmp_unit.height = data["height"]
        tmp_unit.weight = data["weight"]
        tmp_unit.level = data["level"]
        tmp_unit.age = data["age"]
        tmp_unit.deity = data["deity"]
        tmp_unit.hair = data["hair"]
        tmp_unit.eyes = data["eyes"]
        tmp_unit.race = data["race"]
        tmp_unit.gender = data["gender"]
        tmp_unit.homeland = data["homeland"]
        tmp_unit.movementSpeed = data["movementSpeed"]
        tmp_unit.armorSpeed = data["armorSpeed"]
        tmp_unit.flySpeed = data["flySpeed"]
        tmp_unit.flyManeuverability = data["flyManeuverability"]
        tmp_unit.swimSpeed = data["swimSpeed"]
        tmp_unit.climbSpeed = data["climbSpeed"]
        tmp_unit.burrowSpeed = data["burrowSpeed"]

        tmp_unit.STR = data["STR"]
        tmp_unit.DEX = data["DEX"]
        tmp_unit.CON = data["CON"]
        tmp_unit.INT = data["INT"]
        tmp_unit.WIS = data["WIS"]
        tmp_unit.CHA = data["CHA"]
        tmp_unit.STRTemp = data["STRTemp"]
        tmp_unit.DEXTemp = data["DEXTemp"]
        tmp_unit.CONTemp = data["CONTemp"]
        tmp_unit.INTTemp = data["INTTemp"]
        tmp_unit.WISTemp = data["WISTemp"]
        tmp_unit.CHATemp = data["CHATemp"]
        tmp_unit.HP = data["HP"]
        tmp_unit.maxHP = data["maxHP"]
        tmp_unit.DR = data["DR"]
        tmp_unit.wounds = data["wounds"]
        tmp_unit.nonLethal = data["nonLethal"]
        tmp_unit.miscToInit = data["miscToInit"]
        tmp_unit.ACArmor = data["ACArmor"]
        tmp_unit.ACShield = data["ACShield"]
        tmp_unit.ACNatural = data["ACNatural"]
        tmp_unit.ACMisc = data["ACMisc"]
        tmp_unit.deflection = data["deflection"]
        tmp_unit.spellcasting = data["spellcasting"]

        tmp_unit.BAB = data["BAB"]

        tmp_unit.fortBase = data["fortBase"]
        tmp_unit.fortMagic = data["fortMagic"]
        tmp_unit.fortMisc = data["fortMisc"]
        tmp_unit.reflexBase = data["reflexBase"]
        tmp_unit.reflexMagic = data["reflexMagic"]
        tmp_unit.reflexMisc = data["reflexMisc"]
        tmp_unit.willBase = data["willBase"]
        tmp_unit.willMagic = data["willMagic"]
        tmp_unit.willMisc = data["willMisc"]
        tmp_unit.SR = data["SR"]
        tmp_unit.ER = data["ER"]
        tmp_unit.weapons = data["weapons"]
        tmp_unit.skills = data["skills"]
        emit('do_update', ROOMS[room].player_json())


@socketio.on('add_to_initiative')
def on_add_to_initiative(data):
    room = data['room']
    if check_room(room) and ROOMS[room].gmKey == data['gmKey']:
        for x in data["selectedUnits"]:
            if ROOMS[room].unitList[x].type == "player":
                ROOMS[room].unitList[x].requestInit = True
            elif ROOMS[room].unitList[x].controlledBy == "gm":
                ROOMS[room].unitList[x].inInit = True
                ROOMS[room].unitList[x].flatFooted = True
                ROOMS[room].unitList[x].movePath = []
                ROOMS[room].unitList[x].distance = 0
                ROOMS[room].insert_initiative(ROOMS[room].unitList[x])
        ROOMS[room].send_updates()


@socketio.on('change_hp')
def on_change_hp(data):
    room = data['room']
    if check_room(room) and ROOMS[room].gmKey == data['gmKey']:
        if "-" in data['changeHP'] or "+" in data['changeHP']:
            ROOMS[room].initiativeList[data['initCount']].HP = str(
                int(data['changeHP']) + int(ROOMS[room].initiativeList[data['initCount']].HP))
        else:
            ROOMS[room].initiativeList[data['initCount']].HP = data['changeHP']
        ROOMS[room].send_updates()


@socketio.on('reset_movement')
def on_reset_movement(data):
    room = data['room']
    if check_room(room):
        tmpUnit = ROOMS[room].initiativeList[data['selectedInit']]
        if tmpUnit.movePath == []:
            return
        if "gmKey" in data.keys():
            if ROOMS[room].gmKey == data['gmKey']:
                tmpUnit.x = tmpUnit.movePath[0][1]
                tmpUnit.y = tmpUnit.movePath[0][0]
                tmpUnit.location = [tmpUnit.movePath[0][0], tmpUnit.movePath[0][1]]
                tmpUnit.movePath = []
                tmpUnit.distance = 0
            else:
                return
        else:
            if tmpUnit.controlledBy != "gm":
                tmpUnit.x = tmpUnit.movePath[0][1]
                tmpUnit.y = tmpUnit.movePath[0][0]
                tmpUnit.location = [tmpUnit.movePath[0][0], tmpUnit.movePath[0][1]]
                tmpUnit.movePath = []
                tmpUnit.distance = 0
        ROOMS[room].send_updates()


@socketio.on('locate_unit')
def on_locate_unit(data):
    room = data['room']
    if not check_room(room):
        return
    if "selectedUnit" in data.keys():
        tmpUnit = ROOMS[room].unitList[data['selectedUnit']]
    elif "selectedInit" in data.keys():
        tmpUnit = ROOMS[room].initiativeList[data['selectedInit']]
    else:
        return

    if tmpUnit.size == "large":
        if data["relative_y"] > 8:
            data["yCoord"] += 1
        if data["relative_x"] < 8:
            data["xCoord"] -= 1

    if "gmKey" in data.keys() and ROOMS[room].gmKey == data['gmKey']:
        if ROOMS[room].inInit and tmpUnit.inInit and \
                tmpUnit == ROOMS[room].initiativeList[ROOMS[room].initiativeCount]:
            ROOMS[room].calc_path(tmpUnit, (data["yCoord"], data["xCoord"]), data["moveType"])
        else:
            ROOMS[room].calc_path(tmpUnit, (data["yCoord"], data["xCoord"]), 5)
        if tmpUnit.revealsMap:
            revealedTiles = ROOMS[room].reveal_map(tmpUnit.unitNum)
            if revealedTiles:
                emit('gm_map_update', revealedTiles, room=ROOMS[room].gmRoom)
                emit('player_map_update', revealedTiles, room=room)
        ROOMS[room].send_updates()
        return

    # If a player controls, and the unit doesn't have a location, use the player's location as starting location.
    if ROOMS[room].inInit:
        if ROOMS[room].mapArray[data["yCoord"]][data["xCoord"]]["tile"] == "doorClosed" \
                and not ROOMS[room].mapArray[data["yCoord"]][data["xCoord"]]["locked"]:
            ROOMS[room].mapArray[data["yCoord"]][data["xCoord"]]["tile"] = "doorOpen"
            ROOMS[room].send_updates()
        if ROOMS[room].mapArray[data["yCoord"]][data["xCoord"]]["walkable"] \
                and ROOMS[room].mapArray[data["yCoord"]][data["xCoord"]]["seen"] \
                and ROOMS[room].unitList[data['selectedUnit']].controlledBy == data["requestingPlayer"] \
                and ROOMS[room].unitList[data['selectedUnit']].initiative \
                and ROOMS[room].unitList[data['selectedUnit']].initiative == \
                ROOMS[room].initiativeList[ROOMS[room].initiativeCount].initiative:
            if tmpUnit.x != "":
                ROOMS[room].calc_path(tmpUnit, (data["yCoord"], data["xCoord"]), data["moveType"])
            else:
                ROOMS[room].calc_path(tmpUnit, (data["yCoord"], data["xCoord"]), 5)
            if tmpUnit.revealsMap:
                revealedTiles = ROOMS[room].reveal_map(data['selectedUnit'])  # only some controlled units should do this
                emit('gm_map_update', revealedTiles, room=ROOMS[room].gmRoom)
                emit('player_map_update', revealedTiles, room=room)
            ROOMS[room].send_updates()
    else:
        if ROOMS[room].mapArray[data["yCoord"]][data["xCoord"]]["tile"] == "doorClosed" \
                and not ("locked" in ROOMS[room].mapArray[data["yCoord"]][data["xCoord"]] and ROOMS[room].mapArray[data["yCoord"]][data["xCoord"]]["locked"]):
            ROOMS[room].mapArray[data["yCoord"]][data["xCoord"]]["tile"] = "doorOpen"
            ROOMS[room].mapArray[data["yCoord"]][data["xCoord"]]["walkable"] = True
            emit('gm_map_update', [ROOMS[room].mapArray[data["yCoord"]][data["xCoord"]]], room=ROOMS[room].gmRoom)
            emit('player_map_update', [ROOMS[room].mapArray[data["yCoord"]][data["xCoord"]]], room=room)
        if ROOMS[room].mapArray[data["yCoord"]][data["xCoord"]]["walkable"] \
                and ROOMS[room].mapArray[data["yCoord"]][data["xCoord"]]["seen"] \
                and ROOMS[room].unitList[data['selectedUnit']].controlledBy == data["requestingPlayer"]:
            ROOMS[room].calc_path(tmpUnit, (data["yCoord"], data["xCoord"]), 3)
        if tmpUnit.revealsMap:
            revealedTiles = ROOMS[room].reveal_map(data['selectedUnit'])  # only some controlled units should do this
            emit('gm_map_update', revealedTiles, room=ROOMS[room].gmRoom)
            emit('player_map_update', revealedTiles, room=room)
        ROOMS[room].send_updates()


@socketio.on('remove_unit')
def on_remove_unit(data):
    room = data['room']
    if check_room(room) and ROOMS[room].gmKey == data['gmKey'] and ROOMS[room].unitList[
            data['unitCount']].inInit is False:
        ROOMS[room].unitList.pop(data['unitCount'])
        ROOMS[room].number_units()
        ROOMS[room].send_updates()


@socketio.on('remove_init')
def on_remove_init(data):
    room = data['room']
    if check_room(room) and ROOMS[room].gmKey == data['gmKey']:
        if ROOMS[room].inInit and ROOMS[room].initiativeCount > data['initCount']:
            ROOMS[room].initiativeCount -= 1
        elif ROOMS[room].inInit and ROOMS[room].initiativeCount == data['initCount'] and data['initCount'] < len(
                ROOMS[room].initiativeList):
            ROOMS[room].initiativeCount = 0
        ROOMS[room].initiativeList[data['initCount']].inInit = False
        ROOMS[room].initiativeList[data['initCount']].initNum = -1
        ROOMS[room].initiativeList.pop(data['initCount'])
        if len(ROOMS[room].initiativeList) == 0:
            ROOMS[room].inInit = False
        else:
            initNum = 0
            for x in ROOMS[room].initiativeList:
                x.initNum = initNum
                initNum += 1
        ROOMS[room].send_updates()


@socketio.on('del_init')
def on_del_init(data):
    room = data['room']
    if check_room(room) and ROOMS[room].gmKey == data['gmKey']:
        if ROOMS[room].inInit and ROOMS[room].initiativeCount > data['initCount']:
            ROOMS[room].initiativeCount -= 1
        elif ROOMS[room].inInit and ROOMS[room].initiativeCount == data['initCount'] and data['initCount'] == len(
                ROOMS[room].initList) - 1:
            ROOMS[room].initiativeCount = 0
        ROOMS[room].unitList.pop(ROOMS[room].initiativeList[data['initCount']].unitNum)
        ROOMS[room].number_units()
        ROOMS[room].initiativeList.pop(data['initCount'])
        ROOMS[room].send_updates()


@socketio.on('map_generate')
def on_map_generate(data):
    room = data['room']
    if check_room(room) and ROOMS[room].gmKey == data['gmKey']:
        ROOMS[room].mapArray = []
        map_line_list = []
        for y in range(data["mapHeight"]):
            for x in range(data["mapWidth"]):
                map_line_list.append(
                    {"tile": "floorTile", "walkable": True, "seen": data["discovered"], "secret": False, "x": x, "y": y})
            ROOMS[room].mapArray.append(map_line_list)
            map_line_list = []
        ROOMS[room].send_updates()


@socketio.on('map_edit')
def on_map_edit(data_pack):
    room = data_pack['room']
    if check_room(room) and ROOMS[room].gmKey == data_pack['gmKey']:
        updatedTiles = []
        # print(data_pack)
        for data in data_pack["tiles"]:
            if "Tile" in data["newTile"] or "door" in data["newTile"]:
                ROOMS[room].mapArray[data["yCoord"]][data["xCoord"]]["tile"] = data["newTile"]
                if data["newTile"] in ["doorLocked"]:
                    ROOMS[room].mapArray[data["yCoord"]][data["xCoord"]]["locked"] = True
                    ROOMS[room].mapArray[data["yCoord"]][data["xCoord"]]["walkable"] = False
                    ROOMS[room].mapArray[data["yCoord"]][data["xCoord"]]["tile"] = "doorClosed";
                if data["newTile"] in ["doorClosed", "doorTileB"]:
                    ROOMS[room].mapArray[data["yCoord"]][data["xCoord"]]["secret"] = False
                    ROOMS[room].mapArray[data["yCoord"]][data["xCoord"]]["locked"] = False
                if data["newTile"] in ["wallTile", "wallTileA", "wallTileB", "wallTileC", "doorClosed", "doorTileB", "doorLocked"]:
                    ROOMS[room].mapArray[data["yCoord"]][data["xCoord"]]["walkable"] = False
                else:
                    ROOMS[room].mapArray[data["yCoord"]][data["xCoord"]]["walkable"] = True
            elif "stairs" in data["newTile"]:
                ROOMS[room].mapArray[data["yCoord"]][data["xCoord"]]["tile"] = data["newTile"]
                ROOMS[room].mapArray[data["yCoord"]][data["xCoord"]]["secret"] = False
                ROOMS[room].mapArray[data["yCoord"]][data["xCoord"]]["walkable"] = True
            elif data["newTile"] == "secret":
                ROOMS[room].mapArray[data["yCoord"]][data["xCoord"]]["secret"] = not \
                    ROOMS[room].mapArray[data["yCoord"]][data["xCoord"]]["secret"]
            elif data["newTile"] == "seen":
                ROOMS[room].mapArray[data["yCoord"]][data["xCoord"]]["seen"] = not \
                    ROOMS[room].mapArray[data["yCoord"]][data["xCoord"]]["seen"]
            if data["newTile"] in ["doorOpen", "doorTileAOpen", "doorTileBOpen"]:
                for players in ROOMS[room].playerList.keys():
                    revealedTiles = ROOMS[room].reveal_map(ROOMS[room].playerList[players].unitNum)
                    updatedTiles.extend(revealedTiles)
            updatedTiles.append(ROOMS[room].mapArray[data["yCoord"]][data["xCoord"]])
        emit('gm_map_update', updatedTiles)
        tmpUpdatedTiles = copy.deepcopy(updatedTiles)
        for y in tmpUpdatedTiles:
            if not y["seen"]:
                y = {"tile": "unseenTile", "walkable": False}
            elif y["secret"]:
                y = {"tile": "wallTile", "walkable": False}
        emit('player_map_update', tmpUpdatedTiles, room=room)


@socketio.on('map_upload')
def on_map_upload(data):
    room = data['room']
    if check_room(room) and ROOMS[room].gmKey == data['gmKey']:
        ROOMS[room].mapArray = []
        mapText = data['mapText']
        mapLines = mapText.split("\n")
        for y in range(len(mapLines)):
            mapLine = mapLines[y].split("\t")
            map_line_list = []
            for x in range(len(mapLine)):
                if mapLine[x] == "F":
                    map_line_list.append({"tile": "floorTile", "walkable": True})
                elif mapLine[x] == "":
                    map_line_list.append({"tile": "wallTile", "walkable": False})
                elif mapLine[x][0:2] == "SD":
                    map_line_list.append({"tile": "stairsDown", "walkable": True})
                elif mapLine[x][0:2] == "SU":
                    map_line_list.append({"tile": "stairsUp", "walkable": True})
                elif mapLine[x][0] == "D":
                    map_line_list.append({"tile": "doorClosed", "walkable": False})
                    if mapLine[x][:2] == "DS":
                        map_line_list[x]["secret"] = True
                map_line_list[x]["seen"] = data["discovered"]
                map_line_list[x]["x"] = x
                map_line_list[x]["y"] = y
                if "secret" not in map_line_list[x].keys():
                    map_line_list[x]["secret"] = False
            ROOMS[room].mapArray.append(map_line_list)
        ROOMS[room].send_updates()


@socketio.on('earlier_initiative')
def on_earlier_initiative(data):
    room = data['room']
    if check_room(room) and ROOMS[room].gmKey == data['gmKey']:
        if data['targetInitiativeCount'] == 0:
            return
        tmp_data = ROOMS[room].initiativeList.pop(data['targetInitiativeCount'])
        ROOMS[room].initiativeList.insert(data['targetInitiativeCount'] - 1, tmp_data)
        initNum = 0
        for x in ROOMS[room].initiativeList:
            x.initNum = initNum
            initNum += 1
        ROOMS[room].send_updates()


@socketio.on('later_initiative')
def on_later_initiative(data):
    room = data['room']
    if check_room(room) and ROOMS[room].gmKey == data['gmKey']:
        tmpData = ROOMS[room].initiativeList.pop(data['targetInitiativeCount'])
        ROOMS[room].initiativeList.insert(data['targetInitiativeCount'] + 1, tmpData)
        initNum = 0
        for x in ROOMS[room].initiativeList:
            x.initNum = initNum
            initNum += 1
        ROOMS[room].send_updates()


@socketio.on('chat')
def on_chat(data):
    room = data['room']
    if check_room(room):
        if len(data['chat']) == 0:
            return
        if data['charName'] == "gm":
            if ROOMS[room].gmKey == data['gmKey']:
                emit("chat", {'chat': data['chat'], 'charName': data['charName']}, room=room)
                emit("chat", {'chat': data['chat'], 'charName': data['charName']}, room=ROOMS[room].gmRoom)
        else:
            emit("chat", {'chat': data['chat'], 'charName': data['charName']}, room=room)
            emit("chat", {'chat': data['chat'], 'charName': data['charName']}, room=ROOMS[room].gmRoom)
        if data['chat'][0] == "/":
            if "/roll" in data['chat'].lower():
                data['chat'] = roll_dice(data['chat'][5:])
                emit("chat", {'chat': data['chat'], 'charName': data['charName']}, room=room)
                emit("chat", {'chat': data['chat'], 'charName': data['charName']}, room=ROOMS[room].gmRoom)


@socketio.on('create')
def on_create(data):
    """Create a game lobby"""
    room = request.sid
    ROOMS[room] = Session(room, data['gmKey'], data['name'])
    emit("create_room", {'room': room, 'name': data['name'], 'url': "gm.html?gmKey=" + data['gmKey'] + "&room=" + room})


@socketio.on('game_upload')
def on_game_upload(data):
    room = data['room']
    ROOMS[room].from_json(data["saveGame"])
    ROOMS[room].send_updates()


@socketio.on('player_disconnect')
def on_player_disconnect(data):
    room = data['room']
    charName = data['charName']
    if check_room(room) and any(d == charName for d in ROOMS[room].playerList):
        ROOMS[room].playerList[charName].connections -= 1
        if ROOMS[room].playerList[charName].connections < 1:
            ROOMS[room].playerList[charName].connected = False
            # emit("chat", {'chat': charName + " has disconnected", 'charName': "System"}, room=data['room'])
        ROOMS[room].send_updates()


@socketio.on('player_reconnect')
def on_player_reconnect(room, charName):
    if check_room(room) and any(d == charName for d in ROOMS[room].playerList):
        ROOMS[room].playerList[charName].connections -= 1


@socketio.on('add_gp')
def add_gp(room, player, inventory, description, increment, decrement):
    if check_room(room) and player in ROOMS[room].playerList.keys():
        tmpInventory = ROOMS[room].playerList[player].inventories[inventory]["gp"]
        if len(tmpInventory) == 0:
            tmpTotal = 0
        else:
            tmpTotal = tmpInventory[-1]["result"]
        tmpEntry = {}
        tmpEntry["result"] = round(tmpTotal + increment - decrement, 2)
        tmpEntry["description"] = description
        tmpEntry["increment"] = increment
        tmpEntry["decrement"] = decrement
        tmpInventory.append(tmpEntry)
        emit('update_inventory', ROOMS[room].playerList[player].inventories)


@socketio.on('delete_gp_transaction')
def delete_gp(room, player, inventory):
    if check_room(room) and player in ROOMS[room].playerList.keys():
        tmpInventory = ROOMS[room].playerList[player].inventories[inventory]["gp"]
        if len(tmpInventory) == 0:
            return
        else:
            tmpInventory.pop()
            emit('update_inventory', ROOMS[room].playerList[player].inventories)


@socketio.on('add_item')
def add_item(room, player, inventory, data):
    if check_room(room) and player in ROOMS[room].playerList.keys():
        tmpInventory = ROOMS[room].playerList[player].inventories[inventory]["inventory"]
        tmpInventory.append(data)
        emit('update_inventory', ROOMS[room].playerList[player].inventories)


@socketio.on('update_item')
def update_item(room, player, inventory, data):
    if check_room(room) and player in ROOMS[room].playerList.keys():
        tmpItem = ROOMS[room].playerList[player].inventories[inventory]["inventory"][data["invNum"]]
        tmpItem["isWorn"] = data["isWorn"]
        tmpItem["itemCount"] = data["itemCount"]
        tmpItem["itemWeight"] = data["itemWeight"]
        tmpItem["itemValue"] = data["itemValue"]
        emit('update_inventory', ROOMS[room].playerList[player].inventories)


@socketio.on('delete_item')
def delete_item(room, player, inventory, invNum):
    if check_room(room) and player in ROOMS[room].playerList.keys():
        ROOMS[room].playerList[player].inventories[inventory]["inventory"].pop(invNum)
        emit('update_inventory', ROOMS[room].playerList[player].inventories)


@socketio.on('get_inventories')
def get_inventories(room, player):
    if check_room(room) and player in ROOMS[room].playerList.keys():
        emit('update_inventory', ROOMS[room].playerList[player].inventories)


@socketio.on('add_inventory')
def add_inventory(room, player, inventory_name):
    if check_room(room) and player in ROOMS[room].playerList.keys():
        ROOMS[room].playerList[player].inventories[inventory_name] = {}
        ROOMS[room].playerList[player].inventories[inventory_name]['gp'] = []
        ROOMS[room].playerList[player].inventories[inventory_name]['inventory'] = []
        emit('update_inventory', ROOMS[room].playerList[player].inventories)


@socketio.on('del_inventory')
def del_inventory(room, player, inventory_name):
    if check_room(room) and player in ROOMS[room].playerList.keys():
        ROOMS[room].playerList[player].inventories.pop(inventory_name)
        emit('update_inventory', ROOMS[room].playerList[player].inventories)


@socketio.on('delete_player')
def delete_player(room, gmKey, player_name):
    if check_room(room) and gmKey == ROOMS[room].gmKey:
        ROOMS[room].unitList.pop(ROOMS[room].playerList[player_name].unitNum)
        ROOMS[room].playerList.pop(player_name)
        ROOMS[room].number_units()
        ROOMS[room].send_updates()


@socketio.on('error_handle')
def error_handle(room, error_message):
    if check_room(room):
        print("Error Message: ")
        print(error_message)


@socketio.on('database_spells')
def database_spells(casterClass, level):
    conn = sqlite3.connect("mudfinder.sql")
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    q = (level, )
    if casterClass == "Arcanist":
        casterClass = "wiz"
    if casterClass == "Cleric":
        casterClass = "cleric"
    if casterClass in ["wiz", "sor", "cleric", "druid", "ranger", "bard", "paladin", "alchemist", "summoner", "witch", "inquisitor", "oracle", "antipaladin", "magus", "bloodrager", "shaman", "psychic", "medium", "mesmerist", "occultist", "spiritualist", "skald", "investigator", "hunter"]:
        c.execute("select name, school, subschool, descriptor, spell_level, casting_time, components, costly_components, range, area, effect, targets, duration, dismissible, shapeable, saving_throw, spell_resistence, description, short_description, description_formated from spells where %s=?;" % casterClass, q)
    result = [dict(row) for row in c.fetchall()]
    for i in result:
        i["level"] = level
    return result

@socketio.on('database_creatures')
def database_spells(data):
    conn = sqlite3.connect("mudfinder.sql")
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    q = (data["cr"], )
    c.execute("select * from creatures where %s = ?" % "cr", q)
    result = [dict(row) for row in c.fetchall()]
    emit("database_creatures_response", result)

@socketio.on('request_images')
def request_images(room):
    if check_room(room):
        return ROOMS[room].images


@socketio.on('update_effects')
def update_effects(room, effects, gmKey):
    if check_room(room):
        with thread_lock:
            ROOMS[room].effects = effects
        ROOMS[room].send_updates()


def cleanup():
    print("Attempting cleanup")
    thread_lock.acquire()
    for room in ROOMS.keys():
        with open("saves/" + room + ".json", "w") as outfile:
            json.dump(ROOMS[room].gen_save(), outfile)
    print("Bye")


if thread is None:
    thread = socketio.start_background_task(savegame_thread)
atexit.register(cleanup)

if __name__ == '__main__':
    socketio.run(app, debug=False, host='0.0.0.0', port="5000")
