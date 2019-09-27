import copy
import json
import time
import io
import base64
from random import randint

from flask import Flask, render_template, request, redirect
from flask_socketio import SocketIO, join_room, emit

from session import Session


def roll_dice(input_roll_string):
    roll_output = ""
    roll_total: int = 0
    roll_type = ""
    show_totals: bool = False
    totals = ""
    first_time: bool = True
    if '"' in input_roll_string:
        partial_roll_string = input_roll_string[input_roll_string.find('"') + 1:]
        roll_type = partial_roll_string[:partial_roll_string.find('"')]
        input_roll_string = input_roll_string.replace('"' + roll_type + '"', "")
    if '!' in input_roll_string: show_totals = True
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
        if not first_time: roll_output += ", "
        first_time = False
        if show_totals:
            roll_output += totals + "=" + str(roll_total)
        else:
            roll_output += str(roll_total)
    return str(roll_output) + " " + roll_type


# initialize Flask
app = Flask(__name__)
socketio = SocketIO(app)
ROOMS = {}  # dict to track active rooms


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
    if room in ROOMS and ROOMS[room].gmKey == request.args['gmKey']:
        response = app.response_class(
            response=json.dumps(ROOMS[room].gen_save()),
            status=200,
            headers={"Content-disposition":
                         "attachment; filename=" + ROOMS[room].name + ".json"},
            mimetype='application/json'
        )
        return response


@socketio.on('lore_upload')
def on_lore_upload(room, lore_size, lore_name, lore_text):
    if room in ROOMS:
        loreNum = len(ROOMS[room].lore)
        ROOMS[room].lore.append(
            {"loreSize": lore_size, "loreName": lore_name, "loreText": lore_text, "loreVisible": False}
        )
        ROOMS[room].loreFiles[loreNum] = io.BytesIO()
        return loreNum

@socketio.on('write_chunk')
def write_chunk(room, loreNum, offset, data):
    if room in ROOMS:
        ROOMS[room].loreFiles[loreNum].seek(offset)
        ROOMS[room].loreFiles[loreNum].write(data)
        if offset + len(data) >= ROOMS[room].lore[loreNum]["loreSize"]:
            ROOMS[room].loreFiles[loreNum] = base64.b64encode(ROOMS[room].loreFiles[loreNum].getvalue()).decode()


@socketio.on('get_lore_file')
def get_lore_file(room, loreNum):
    if room in ROOMS:
        return ROOMS[room].loreFiles[loreNum]
        #return base64.b64encode(ROOMS[room].loreFiles[loreNum].getvalue()).decode()


@socketio.on('lore_url')
def on_lore_url(room, lore_url, lore_name, lore_text):
    if room in ROOMS:
        ROOMS[room].lore.append(
            {"loreURL": lore_url, "loreName": lore_name, "loreText": lore_text, "loreVisible": False, "loreSize": 0})
        emit("showLore", {"lore": ROOMS[room].lore, "lore_num": None}, room=room)


@socketio.on('lore_visible')
def on_lore_visible(room, gmKey, lore_num):
    print(lore_num)
    if room in ROOMS and ROOMS[room].gmKey == gmKey:
        ROOMS[room].lore[lore_num]["loreVisible"] = not ROOMS[room].lore[lore_num]["loreVisible"]
        if not ROOMS[room].lore[lore_num]["loreVisible"]:
            lore_num = None
        emit("showLore", {"lore": ROOMS[room].lore, "lore_num": lore_num}, room=room)


@socketio.on('delete_lore')
def on_delete_lore(room, gmKey, lore_num):
    if room in ROOMS and ROOMS[room].gmKey == gmKey:
        ROOMS[room].lore.pop(lore_num)
        tmp_keys = []
        for x in ROOMS[room].loreFiles:
            tmp_keys.append(x)
        for x in tmp_keys:
            if x > lore_num:
                ROOMS[room].loreFiles[x-1] = ROOMS[room].loreFiles[x]
        emit("showLore", {"lore": ROOMS[room].lore, "lore_num": None}, room=room)


@socketio.on('get_lore')
def on_get_lore(room):
    if room in ROOMS:
        emit("showLore", {"lore": ROOMS[room].lore, "lore_num": None})


@socketio.on('player_join')
def on_player_join(data):
    """Join a game lobby"""
    room = data['room']
    if room in ROOMS:
        join_room(room)
        if not any(d == data['charName'] for d in ROOMS[room].playerList):  # TODO: make this a class function
            ROOMS[room].playerList[
                data['charName']] = data  # ({"charName": data['charName'], "sid": request.sid, "requestInit": False})
            ROOMS[room].playerList[data['charName']]["requestInit"] = False
            ROOMS[room].playerList[data['charName']]["inventories"] = {}
            ROOMS[room].playerList[data['charName']]["inventories"][data['charName']] = {}
            ROOMS[room].playerList[data['charName']]["inventories"][data['charName']]["gp"] = []
            ROOMS[room].playerList[data['charName']]["inventories"][data['charName']]["inventory"] = []

            ROOMS[room].playerList[data['charName']]["connections"] = 0
            ROOMS[room].playerList[data['charName']]["revealsMap"] = True
            ROOMS[room].playerList[data['charName']]["controlledBy"] = ROOMS[room].playerList[data['charName']][
                "charName"]
            ROOMS[room].unitList.append(ROOMS[room].playerList[data['charName']])

        if "connections" not in  ROOMS[room].playerList[data['charName']]:  # Can be removed once versioning is a thing
            ROOMS[room].playerList[data['charName']]["connections"] = 0
        if "inventories" not in  ROOMS[room].playerList[data['charName']]:
            ROOMS[room].playerList[data['charName']]["inventories"] = {}
            ROOMS[room].playerList[data['charName']]["inventories"][data['charName']] = {}
            ROOMS[room].playerList[data['charName']]["inventories"][data['charName']]["gp"] = []
            ROOMS[room].playerList[data['charName']]["inventories"][data['charName']]["inventory"] = []

        ROOMS[room].playerList[data['charName']]["sid"] = request.sid
        ROOMS[room].playerList[data['charName']]["type"] = "player"
        ROOMS[room].playerList[data['charName']]["connections"] += 1
        ROOMS[room].playerList[data['charName']]["connected"] = True
        ROOMS[room].number_units()
        emit('do_update', ROOMS[room].player_json(), room=room)
    else:
        emit('error', {'error': 'Unable to join room. Room does not exist.'})


@socketio.on('spectator_join')
def on_spectator_join(data):
    """Join a game lobby"""
    room = data['room']
    if room in ROOMS:
        join_room(room)
        emit('do_update', ROOMS[room].player_json(), room=room)
    else:
        emit('error', {'error': 'Unable to join room. Room does not exist.'})


@socketio.on('gm_update')
def on_gm_update(data):
    """gm session update"""
    room = data['room']
    if room in ROOMS and ROOMS[room].gmKey == data['gmKey']:
        emit('gm_update', ROOMS[room].to_json())


@socketio.on('join_gm')
def on_join_gm(data):
    """Join a game as GM"""
    room = data['room']
    if room in ROOMS and ROOMS[room].gmKey == data['gmKey']:
        join_room(room)
        emit('gm_update', ROOMS[room].to_json())
    else:
        emit('error', {'error': 'Unable to join room. Room does not exist.'})


@socketio.on('request_init')
def on_request_init(data):
    """request initiative"""
    room = data['room']
    if room in ROOMS and ROOMS[room].gmKey == data['gmKey']:
        for d in ROOMS[room].playerList:
            ROOMS[room].playerList[d]["requestInit"] = True
        emit('do_update', ROOMS[room].player_json(), room=room)


@socketio.on('send_initiative')
def on_initiative(data):
    """recieve initiative"""
    room = data['room']
    if room in ROOMS:
        ROOMS[room].playerList[data['charName']]["requestInit"] = False
        for x in ROOMS[room].unitList:
            if x["controlledBy"] == data['charName']:
                x["initiative"] = data["initiative"].pop(0)
                x["inInit"] = True
                x["movePath"] = []
                x["distance"] = 0
                ROOMS[room].insert_initiative(x)
        emit('do_update', ROOMS[room].player_json(), room=room)


@socketio.on('begin_init')
def on_begin_init(data):
    """begin initiative"""
    room = data['room']
    if room in ROOMS and ROOMS[room].gmKey == data['gmKey']:
        ROOMS[room].inInit = True
        ROOMS[room].initiativeCount = 0
        emit('do_update', ROOMS[room].player_json(), room=room)


@socketio.on('advance_init')
def on_advance_init(data):
    room = data['room']
    if room in ROOMS:
        if ("gmKey" in data and ROOMS[room].gmKey == data['gmKey']) or \
                ROOMS[room].initiativeList[ROOMS[room].initiativeCount]["controlledBy"] == data["charName"]:
            ROOMS[room].initiativeCount += 1
            if ROOMS[room].initiativeCount >= len(ROOMS[room].initiativeList):
                ROOMS[room].initiativeCount = 0
            ROOMS[room].initiativeList[ROOMS[room].initiativeCount]["movePath"] = []
            ROOMS[room].initiativeList[ROOMS[room].initiativeCount]["distance"] = 0
            emit('do_update', ROOMS[room].player_json(), room=room)


@socketio.on('end_init')
def on_end_init(data):
    room = data['room']
    if room in ROOMS and ROOMS[room].gmKey == data['gmKey']:
        ROOMS[room].inInit = False
        for x in ROOMS[room].unitList:
            x["inInit"] = False
            x["movePath"] = []
            x["distance"] = 0
        ROOMS[room].initiativeCount = 0
        ROOMS[room].initiativeList = []
        emit('do_update', ROOMS[room].player_json(), room=room)


@socketio.on('save_encounter')
def on_save_encounter(data):
    room = data['room']
    if room in ROOMS and ROOMS[room].gmKey == data['gmKey']:
        ROOMS[room].savedEncounters[data['encounterName']] = {}
        ROOMS[room].savedEncounters[data['encounterName']]["mapArray"] = copy.deepcopy(ROOMS[room].mapArray)
        ROOMS[room].savedEncounters[data['encounterName']]["unitList"] = []
        for x in ROOMS[room].unitList:
            if x["controlledBy"] == "gm":
                ROOMS[room].savedEncounters[data['encounterName']]["unitList"].append(x)
        emit('do_update', ROOMS[room].player_json(), room=room)


@socketio.on('remove_encounter')
def on_remove_encounter(data):
    room = data['room']
    if room in ROOMS and ROOMS[room].gmKey == data['gmKey']:
        ROOMS[room].savedEncounters.pop(data['encounterName'])
        emit('do_update', ROOMS[room].player_json(), room=room)


@socketio.on('load_encounter')
def on_load_encounter(data):
    room = data['room']
    if room in ROOMS and ROOMS[room].gmKey == data['gmKey']:
        ROOMS[room].mapArray = copy.deepcopy(ROOMS[room].savedEncounters[data['encounterName']]["mapArray"])
        for x in reversed(ROOMS[room].unitList):
            if x["controlledBy"] == "gm":
                ROOMS[room].unitList.remove(x)
            else:
                if data["clearLocations"] and "x" in x.keys():
                    x.pop("x")
                    x.pop("y")
        for x in ROOMS[room].savedEncounters[data['encounterName']]["unitList"]:
            ROOMS[room].unitList.append(copy.deepcopy(x))
        ROOMS[room].number_units()
        emit('do_update', ROOMS[room].player_json(), room=room)


@socketio.on('add_player_unit')
def on_add_player_unit(data):
    room = data['room']
    if room in ROOMS:
        unit = data['unit']
        unit["controlledBy"] = data["charName"]
        if ROOMS[room].inInit:
            unit["initiative"] = ROOMS[room].playerList[data["charName"]]["initiative"]
        ROOMS[room].unitList.append(data['unit'])
        ROOMS[room].number_units()
        emit('do_update', ROOMS[room].player_json(), room=room)


@socketio.on('clear_map')
def on_clear_map(data):
    room = data['room']
    if room in ROOMS and ROOMS[room].gmKey == data['gmKey']:
        ROOMS[room].mapArray = []
        ROOMS[room].inInit = False
        for x in reversed(ROOMS[room].unitList):  # since we're removing elements, have to walk it backwards
            if x["controlledBy"] == "gm":
                ROOMS[room].unitList.remove(x)
            else:
                x["inInit"] = False
                if data["clearLocations"] and "x" in x.keys():
                    x.pop("x")
                    x.pop("y")
        ROOMS[room].initiativeCount = 0
        ROOMS[room].initiativeList = []
        ROOMS[room].number_units()
        emit('do_update', ROOMS[room].player_json(), room=room)


@socketio.on('add_unit')
def on_add_unit(data):
    room = data['room']
    if room in ROOMS and ROOMS[room].gmKey == data['gmKey']:
        data['unit']["movePath"] = []
        data['unit']["distance"] = 0
        ROOMS[room].unitList.append(data['unit'])
        if data["addToInitiative"]:
            ROOMS[room].insert_initiative(ROOMS[room].unitList[-1])
            ROOMS[room].unitList[-1]["inInit"] = True
        ROOMS[room].number_units()
        emit('do_update', ROOMS[room].player_json(), room=room)


@socketio.on('update_unit')
def on_update_unit(data):
    room = data['room']
    if room in ROOMS:
        tmp_unit = ROOMS[room].unitList[int(data["unitNum"])]
        tmp_unit["charShortName"] = data["charShortName"]
        tmp_unit["color"] = data["color"]
        tmp_unit["perception"] = data["perception"]
        tmp_unit["movementSpeed"] = data["movementSpeed"]
        tmp_unit["dex"] = data["dex"]
        tmp_unit["size"] = data["size"]
        tmp_unit["darkvision"] = data["darkvision"]
        tmp_unit["lowLight"] = data["lowLight"]
        tmp_unit["trapfinding"] = data["trapfinding"]
        tmp_unit["hasted"] = data["hasted"]
        tmp_unit["permanentAbilities"] = data["permanentAbilities"]
        if "gmKey" in data.keys() and ROOMS[room].gmKey == data['gmKey']:
            tmp_unit["revealsMap"] = data["revealsMap"]
            tmp_unit["initiative"] = data["initiative"]
        emit('do_update', ROOMS[room].player_json(), room=room)


@socketio.on('add_to_initiative')
def on_add_to_initiative(data):
    room = data['room']
    if room in ROOMS and ROOMS[room].gmKey == data['gmKey']:
        for x in data["selectedUnits"]:
            ROOMS[room].unitList[x]["inInit"] = True
            ROOMS[room].unitList[x]["movePath"] = []
            ROOMS[room].unitList[x]["distance"] = 0
            ROOMS[room].insert_initiative(ROOMS[room].unitList[x])
        emit('do_update', ROOMS[room].player_json(), room=room)


@socketio.on('change_hp')
def on_change_hp(data):
    room = data['room']
    if room in ROOMS and ROOMS[room].gmKey == data['gmKey']:
        if "-" in data['changeHP'] or "+" in data['changeHP']:
            ROOMS[room].initiativeList[data['initCount']]["HP"] = str(
                int(data['changeHP']) + int(ROOMS[room].initiativeList[data['initCount']]["HP"]))
        else:
            ROOMS[room].initiativeList[data['initCount']]["HP"] = data['changeHP']
        emit('do_update', ROOMS[room].player_json(), room=room)


@socketio.on('reset_movement')
def on_reset_movement(data):
    room = data['room']
    if room in ROOMS:
        tmpUnit = ROOMS[room].initiativeList[data['selectedInit']]
        if "gmKey" in data.keys():
            if ROOMS[room].gmKey == data['gmKey']:
                tmpUnit["x"] = tmpUnit["movePath"][0][0]
                tmpUnit["y"] = tmpUnit["movePath"][0][1]
                tmpUnit["movePath"] = []
                tmpUnit["distance"] = 0
            else:
                return
        else:
            if tmpUnit["controlledBy"] != "gm":
                tmpUnit["x"] = tmpUnit["movePath"][0][0]
                tmpUnit["y"] = tmpUnit["movePath"][0][1]
                tmpUnit["movePath"] = []
                tmpUnit["distance"] = 0
        emit('do_update', ROOMS[room].player_json(), room=room)


@socketio.on('locate_unit')
def on_locate_unit(data):
    startTime = time.time()
    room = data['room']
    if room in ROOMS:  # and ROOMS[room].gmKey == data['gmKey']:
        if "selectedUnit" in data.keys():
            tmpUnit = ROOMS[room].unitList[data['selectedUnit']]  # can also be selectedInit
        elif "selectedInit" in data.keys():
            tmpUnit = ROOMS[room].initiativeList[data['selectedInit']]  # can also be selectedInit
        else:
            return
        if "gmKey" in data.keys() and ROOMS[room].gmKey == data['gmKey']:
            if ROOMS[room].inInit and tmpUnit["inInit"] and \
                    tmpUnit == ROOMS[room].initiativeList[ROOMS[room].initiativeCount] and \
                    "x" in tmpUnit.keys():
                ROOMS[room].calc_path(tmpUnit, (data["xCoord"], data["yCoord"]), data["moveType"])
            else:
                ROOMS[room].calc_path(tmpUnit, (data["xCoord"], data["yCoord"]), 5)
            if "revealsMap" in tmpUnit.keys() and tmpUnit["revealsMap"]:
                ROOMS[room].reveal_map(tmpUnit["unitNum"])
            emit('do_update', ROOMS[room].player_json(), room=room)
            print(time.time() - startTime)
            return
        if ROOMS[room].inInit:
            if ROOMS[room].mapArray[data["xCoord"]][data["yCoord"]]["walkable"] \
                    and ROOMS[room].mapArray[data["xCoord"]][data["yCoord"]]["seen"] \
                    and ROOMS[room].unitList[data['selectedUnit']]["controlledBy"] == data["requestingPlayer"] \
                    and ROOMS[room].unitList[data['selectedUnit']]["initiative"] \
                    and ROOMS[room].unitList[data['selectedUnit']]["initiative"] == \
                    ROOMS[room].initiativeList[ROOMS[room].initiativeCount]["initiative"]:
                if "x" in tmpUnit.keys():
                    ROOMS[room].calc_path(tmpUnit, (data["xCoord"], data["yCoord"]), data["moveType"])
                else:
                    ROOMS[room].unitList[data['selectedUnit']]['x'] = data["xCoord"]
                    ROOMS[room].unitList[data['selectedUnit']]['y'] = data["yCoord"]
                if "revealsMap" in tmpUnit.keys() and tmpUnit["revealsMap"]:
                    ROOMS[room].reveal_map(data['selectedUnit'])  # only some controlled units should do this
                emit('do_update', ROOMS[room].player_json(), room=room)
        elif ROOMS[room].mapArray[data["xCoord"]][data["yCoord"]]["walkable"] \
                and ROOMS[room].mapArray[data["xCoord"]][data["yCoord"]]["seen"] \
                and ROOMS[room].unitList[data['selectedUnit']]["controlledBy"] == data["requestingPlayer"]:
            ROOMS[room].unitList[data['selectedUnit']]['x'] = data["xCoord"]
            ROOMS[room].unitList[data['selectedUnit']]['y'] = data["yCoord"]
            if "revealsMap" in tmpUnit.keys() and tmpUnit["revealsMap"]:
                ROOMS[room].reveal_map(data['selectedUnit'])  # only some controlled units should do this
            emit('do_update', ROOMS[room].player_json(), room=room)


@socketio.on('remove_unit')
def on_remove_unit(data):
    room = data['room']
    if room in ROOMS and ROOMS[room].gmKey == data['gmKey'] and ROOMS[room].unitList[data['unitCount']][
        "inInit"] == False:
        ROOMS[room].unitList.pop(data['unitCount'])
        ROOMS[room].number_units()
        emit('do_update', ROOMS[room].player_json(), room=room)


@socketio.on('remove_init')
def on_remove_init(data):
    room = data['room']
    if room in ROOMS and ROOMS[room].gmKey == data['gmKey']:
        if ROOMS[room].inInit and ROOMS[room].initiativeCount > data['initCount']:
            ROOMS[room].initiativeCount -= 1
        elif ROOMS[room].inInit and ROOMS[room].initiativeCount == data['initCount'] and data['initCount'] < len(
                data["initList"]):
            ROOMS[room].initiativeCount = 0
        ROOMS[room].initiativeList[data['initCount']]["inInit"] = False
        ROOMS[room].initiativeList.pop(data['initCount'])
        emit('do_update', ROOMS[room].player_json(), room=room)


@socketio.on('del_init')
def on_del_init(data):
    room = data['room']
    if room in ROOMS and ROOMS[room].gmKey == data['gmKey']:
        if ROOMS[room].inInit and ROOMS[room].initiativeCount > data['initCount']:
            ROOMS[room].initiativeCount -= 1
        elif ROOMS[room].inInit and ROOMS[room].initiativeCount == data['initCount'] and data['initCount'] < len(
                data["initList"]):
            ROOMS[room].initiativeCount = 0
        ROOMS[room].unitList.pop(ROOMS[room].initiativeList[data['initCount']]["unitNum"])
        ROOMS[room].number_units()
        ROOMS[room].initiativeList.pop(data['initCount'])
        emit('do_update', ROOMS[room].player_json(), room=room)


@socketio.on('map_generate')
def on_map_generate(data):
    room = data['room']
    if room in ROOMS and ROOMS[room].gmKey == data['gmKey']:
        ROOMS[room].mapArray = []
        map_line_list = []
        for y in range(data["mapHeight"]):
            for x in range(data["mapWidth"]):
                map_line_list.append(
                    {"tile": "floorTile", "walkable": True, "seen": data["discovered"], "secret": False})
            ROOMS[room].mapArray.append(map_line_list)
            map_line_list = []
        emit('do_update', ROOMS[room].player_json(), room=room)


@socketio.on('map_edit')
def on_map_edit(data_pack):
    room = data_pack['room']
    if room in ROOMS and ROOMS[room].gmKey == data_pack['gmKey']:
        for data in data_pack["tiles"]:
            if "Tile" in data["newTile"] or "door" in data["newTile"]:
                ROOMS[room].mapArray[data["xCoord"]][data["yCoord"]]["tile"] = data["newTile"]
                if data["newTile"] in ["doorClosed", "doorTileB"]:
                    ROOMS[room].mapArray[data["xCoord"]][data["yCoord"]]["secret"] = False
                if data["newTile"] in ["wallTile", "wallTileA", "wallTileB", "wallTileC", "doorClosed", "doorTileB"]:
                    ROOMS[room].mapArray[data["xCoord"]][data["yCoord"]]["walkable"] = False
                else:
                    ROOMS[room].mapArray[data["xCoord"]][data["yCoord"]]["walkable"] = True
            elif "stairs" in data["newTile"]:
                ROOMS[room].mapArray[data["xCoord"]][data["yCoord"]]["tile"] = data["newTile"]
                ROOMS[room].mapArray[data["xCoord"]][data["yCoord"]]["secret"] = False
                ROOMS[room].mapArray[data["xCoord"]][data["yCoord"]]["walkable"] = True
            elif data["newTile"] == "secret":
                ROOMS[room].mapArray[data["xCoord"]][data["yCoord"]]["secret"] = not \
                    ROOMS[room].mapArray[data["xCoord"]][data["yCoord"]]["secret"]
            elif data["newTile"] == "seen":
                ROOMS[room].mapArray[data["xCoord"]][data["yCoord"]]["seen"] = not \
                    ROOMS[room].mapArray[data["xCoord"]][data["yCoord"]]["seen"]
            if data["newTile"] in ["doorOpen", "doorTileAOpen", "doorTileBOpen"]:
                for players in ROOMS[room].playerList.keys():
                    ROOMS[room].reveal_map(ROOMS[room].playerList[players]["unitNum"])
        emit('do_update', ROOMS[room].player_json(), room=room)


@socketio.on('map_upload')
def on_map_upload(data):
    room = data['room']
    if room in ROOMS and ROOMS[room].gmKey == data['gmKey']:
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
                if "secret" not in map_line_list[x].keys():
                    map_line_list[x]["secret"] = False
            ROOMS[room].mapArray.append(map_line_list)
        emit('do_update', ROOMS[room].player_json(), room=room)


@socketio.on('earlier_initiative')
def on_earlier_initiative(data):
    room = data['room']
    if room in ROOMS and ROOMS[room].gmKey == data['gmKey']:
        if data['targetInitiativeCount'] == 0: return
        tmp_data = ROOMS[room].initiativeList.pop(data['targetInitiativeCount'])
        ROOMS[room].initiativeList.insert(data['targetInitiativeCount'] - 1, tmp_data)
        emit('do_update', ROOMS[room].player_json(), room=room)


@socketio.on('later_initiative')
def on_later_initiative(data):
    room = data['room']
    if room in ROOMS and ROOMS[room].gmKey == data['gmKey']:
        tmpData = ROOMS[room].initiativeList.pop(data['targetInitiativeCount'])
        ROOMS[room].initiativeList.insert(data['targetInitiativeCount'] + 1, tmpData)
        emit('do_update', ROOMS[room].player_json(), room=room)


@socketio.on('chat')
def on_chat(data):
    room = data['room']
    if room in ROOMS:
        if data['charName'] == "gm":
            if ROOMS[room].gmKey == data['gmKey']:
                emit("chat", {'chat': data['chat'], 'charName': data['charName']}, room=data['room'])
        else:
            emit("chat", {'chat': data['chat'], 'charName': data['charName']}, room=data['room'])
        if data['chat'][0] == "/":
            if "/roll" in data['chat'].lower():
                emit("chat", {'chat': roll_dice(data['chat'][5:]), 'charName': "DiceBot"}, room=data['room'])


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
    emit('do_update', ROOMS[room].player_json(), room=room)


@socketio.on('player_disconnect')
def on_player_disconnect(data):
    room = data['room']
    charName = data['charName']
    if room in ROOMS and any(d == charName for d in ROOMS[room].playerList):
        ROOMS[room].playerList[charName]["connections"] -= 1
        if ROOMS[room].playerList[charName]["connections"] < 1:
            ROOMS[room].playerList[charName]["connected"] = False
            emit("chat", {'chat': charName + " has disconnected", 'charName': "System"}, room=data['room'])
        emit('do_update', ROOMS[room].player_json(), room=room)


@socketio.on('add_gp')
def add_gp(room, player, inventory, description, increment, decrement):
    if room in ROOMS and player in ROOMS[room].playerList.keys():
        tmpInventory = ROOMS[room].playerList[player]["inventories"][inventory]["gp"]
        if len(tmpInventory) == 0:
            tmpTotal = 0
        else:
            tmpTotal = tmpInventory[-1]["result"]
        tmpEntry = {}
        tmpEntry["result"] = tmpTotal + increment - decrement
        tmpEntry["description"] = description
        tmpEntry["increment"] = increment
        tmpEntry["decrement"] = decrement
        tmpInventory.append(tmpEntry)
        emit('update_inventory', ROOMS[room].playerList[player]["inventories"])


@socketio.on('delete_gp_transaction')
def delete_gp(room, player, inventory):
    if room in ROOMS and player in ROOMS[room].playerList.keys():
        tmpInventory = ROOMS[room].playerList[player]["inventories"][inventory]["gp"]
        if len(tmpInventory) == 0:
            return
        else:
            tmpInventory.pop()
            emit('update_inventory', ROOMS[room].playerList[player]["inventories"])


@socketio.on('add_item')
def add_item(room, player, inventory, data):
    if room in ROOMS and player in ROOMS[room].playerList.keys():
        tmpInventory = ROOMS[room].playerList[player]["inventories"][inventory]["inventory"]
        tmpInventory.append(data)
        emit('update_inventory', ROOMS[room].playerList[player]["inventories"])

@socketio.on('update_item')
def update_item(room, player, inventory, data):
    if room in ROOMS and player in ROOMS[room].playerList.keys():
        tmpItem = ROOMS[room].playerList[player]["inventories"][inventory]["inventory"][data["invNum"]]
        tmpItem["isWorn"] = data["isWorn"]
        tmpItem["itemCount"] = data["itemCount"]
        emit('update_inventory', ROOMS[room].playerList[player]["inventories"])


@socketio.on('delete_item')
def delete_item(room, player, inventory, invNum):
    if room in ROOMS and player in ROOMS[room].playerList.keys():
        ROOMS[room].playerList[player]["inventories"][inventory]["inventory"].pop(invNum)
        emit('update_inventory', ROOMS[room].playerList[player]["inventories"])


@socketio.on('get_inventories')
def get_inventories(room, player):
    if room in ROOMS and player in ROOMS[room].playerList.keys():
        emit('update_inventory', ROOMS[room].playerList[player]["inventories"])

if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port="5000")
