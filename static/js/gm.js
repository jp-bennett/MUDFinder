var selectedInitiative;
var selectedUnits = [];
var gmData;
var zoomSize = 20;
var selectedTool;
var socket;
showSeenOverlay = true;
window.onload = function() {
socket = io.connect('http://' + document.domain + ':' + location.port, {'sync disconnect on unload': true, transports: ['websocket'], upgrade: false});
socket.on('connect', function() {
    console.log('Websocket connected!');
    if (typeof window.location.search.split("&")[1] != "undefined") {
        gmKey=window.location.search.split("&")[0].split("=")[1];
        room=window.location.search.split("&")[1].split("=")[1];
        socket.emit('join_gm', {room: room, gmKey: gmKey});
        document.getElementById("linkDiv").innerHTML = 'New session created!' +
        ` Players can use <a href="player.html?room=${room}">this link!</a><br>` +
        ` Spectators can use <a href="spectator.html?room=${room}">this link!</a>`;
    }
});
socket.on('chat', function(msg) {
    console.log(msg);
    now = new Date;
    document.getElementById("chatText").innerText += "[" + now.getHours().toString().padStart(2, '0') + ":" + now.getMinutes().toString().padStart(2, '0') +
    ":" + now.getSeconds().toString().padStart(2, '0') + "] " + msg["charName"] + ": " + msg["chat"];
    document.getElementById("chatText").innerHTML += "<br />";
    document.getElementById("chatText").scrollTop = document.getElementById("chatText").scrollHeight;
});

socket.on('gm_update', function(msg) {
    console.log("updating the GM data");
    gmData = msg;
    console.log(gmData);
    document.title = gmData.name
    updateMap(gmData);
    // populate units
    document.getElementById("unitsDiv").innerHTML = "";

    if (typeof selectedInitiative !== "undefined") {
        populateEditChar(gmData, gmData.initiativeList[selectedInitiative].unitNum)
    } else if (typeof selectedUnits[0] !== "undefined") {
        populateEditChar(gmData, selectedUnits[0])
    } else {
        populateEditChar(gmData, 0)
    }

    for (var i = 0; i < gmData.unitList.length; i++) {
        tmpUnit = `
          <div style="display:flex;">
             <div onclick="selectUnit(event, ${i})" `;
               if (selectedUnits.includes(i)) {
                   tmpUnit += 'class="selected"'
               } else {
                   tmpUnit += 'class="nonSelected"'
               }
               tmpUnit += `style="width:100%;">
              <div style="float:left; padding:7px;">  ${gmData.unitList[i].charName}
              </div>
                <div style="float:right;">`;
                  if (gmData.unitList[i].type !== "player" && !gmData.unitList[i].inInit) {
                    tmpUnit +=`<button onclick="removeUnit(event, ${i})">
                      Remove
                    </button>`;
                  }
                tmpUnit +=`</div>
              </div>
              <div id="activeInit">
            </div>
          </div>`;
        document.getElementById("unitsDiv").innerHTML += tmpUnit
    }

    document.getElementById("initiativeDiv").innerHTML = "";
    for (var i = 0; i < gmData.initiativeList.length; i++) {
        tmpHTML = `
          <div style="display:flex;">
             <div onclick="selectInitiative(${i})"`;
             if (typeof selectedInitiative !== "undefined" && selectedInitiative == i) {
                 tmpHTML += 'class="selectedInit">';
             } else {
                 tmpHTML += 'class="nonSelectedInit">';
             }
              tmpHTML += `<div style="float:left; padding:7px;">  ${gmData.initiativeList[i].charName}
              </div>
              <div style="float:left; padding:7px;">  ${(gmData.initiativeList[i].HP != null) ? gmData.initiativeList[i].HP + "/" + gmData.initiativeList[i].maxHP : "" }
              </div>
              <div style="float:left; padding:6px;">
                <form action="javascript:changeHP(${i})">
                  <input onclick="event.stopPropagation();" type="text" id="hpChange${i}" style="width:25px;"></input>
                </form>
              </div>
                <div style="float:right; width:120px;">  ${gmData.initiativeList[i].initiative}
                  <button onclick="removeInit(event, ${i})">
                    Rem
                  </button>`;
                  if (gmData.initiativeList[i].type !== "player") {
                    tmpHTML += `<button onclick="delInit(event, ${i})">
                                  Del
                                </button>`;
                  }
                tmpHTML += `</div>
                <div style="float:right;"> <span style="cursor: default;" onclick="earlierInit(event, ${i})">&#9650;</span> <br> <span style="cursor: default;" onclick="laterInit(event, ${i})">&#9660;</span></div>
              </div>
              <div id="activeInit"><--
            </div>
          </div>`;
        document.getElementById("initiativeDiv").innerHTML += tmpHTML;
    }

    if (gmData.inInit) { activeInitiative(gmData.initiativeCount)} //this value counts from 1

    // Initiative controls
    if (gmData.inInit) {
        document.getElementById("movementButton").style.display = "block";
        document.getElementById("movementDiv").style.display = "block";
        document.getElementById("beginInit").style.display = "none";
        document.getElementById("advanceInit").style.display = "block";
        document.getElementById("endInit").style.display = "block";
    } else {
        document.getElementById("movementButton").style.display = "none";
        document.getElementById("movementDiv").style.display = "none";
        document.getElementById("beginInit").style.display = "block";
        document.getElementById("advanceInit").style.display = "none";
        document.getElementById("endInit").style.display = "none";
    }
    //populate saved encounters
    document.getElementById("encountersDiv").innerHTML = "";
    for (var i = 0; i < Object.keys(gmData.savedEncounters).length; i++) {
        document.getElementById("encountersDiv").innerHTML += `<div onclick="clickEncounter(this)" id="${Object.keys(gmData.savedEncounters)[i]}">` +
        Object.keys(gmData.savedEncounters)[i] + `<button onclick="removeEncounter('${Object.keys(gmData.savedEncounters)[i]}')">X</button></div>`;
    }
    // populate player list
    document.getElementById("links").innerHTML = "Links<br>";
    document.getElementById("connectedPlayers").innerHTML = "";
    document.getElementById("unitControlledBy").innerHTML =  '<option value="gm" selected="selected">gm</option>';
    for (var i = 0; i < Object.keys(gmData.playerList).length; i++) {
        tmpPlayerName = Object.keys(gmData.playerList)[i];
        document.getElementById("links").innerHTML += `<a href="player.html?room=${room}&charName=${tmpPlayerName}">${tmpPlayerName}</a><br>`
        if (gmData.playerList[tmpPlayerName].connected) {
            document.getElementById("unitControlledBy").innerHTML += `<option value="${tmpPlayerName}">${tmpPlayerName}</option>`;
            document.getElementById("connectedPlayers").innerHTML += tmpPlayerName + "<br >";
        }
    }
});

socket.on('do_update', function(msg) {
    console.log("Request GM Update");
    socket.emit('gm_update', {room: room, gmKey: gmKey});
});

} // end onload
function mapInput() {
    mapText = document.getElementById('mapText').value;
    socket.emit('map_upload', {mapText: mapText, mapTextType:"csv", discovered: document.getElementById("mapIsDiscovered").checked, gmKey: gmKey, room: room});
}
function saveGameInput() {
    gameObj = JSON.parse(document.getElementById('saveGameText').value);
    console.log(gameObj);
    socket.emit('game_upload', {saveGame: gameObj, mapTextType:"csv", discovered: document.getElementById("mapIsDiscovered").checked, gmKey: gmKey, room: room});
}
function downloadGame() {
    window.location = "download.html?gmKey=" + gmKey + "&room=" + room;
}
function mapGenerate() {
    mapWidth = parseInt(document.getElementById('mapWidth').value);
    mapHeight = parseInt(document.getElementById('mapHeight').value);
    socket.emit('map_generate', {mapWidth: mapWidth, mapHeight: mapHeight, discovered: document.getElementById("mapIsDiscovered").checked, gmKey: gmKey, room: room});
}
function mapTool(e, tileName) {
    if (typeof selectedTool !== "undefined" && selectedTool == e.target) {
        deselectAll();
        return;
    }
    deselectAll();
    e.target.parentElement.className="selected"
    selectedTool = e.target;
}
function seenOverlayToggle(obj) {
  console.log(obj);
  if(obj.checked) {
    showSeenOverlay = true;
  } else {
    showSeenOverlay = false;
  }
  updateMap(gmData);
}
function sendChat() {
    socket.emit('chat', {chat: document.getElementById('newChat').value, charName: "gm", gmKey: gmKey, room: room});
    document.getElementById('newChat').value = "";
}
function sendMessage() {
    console.log('Sending...');
    console.log(room);
    socket.emit('chat', {chat: document.getElementById("message").value, room: room});
}
function requestInit() {
    console.log('requesting initiative');
    socket.emit('request_init', {gmKey: gmKey, room: room});
}
function addUnit() {
    var unit = {};
    unit.charName = document.getElementById("unitName").value;
    unit.charShortName = document.getElementById("unitShortName").value;
    unit.initiative = document.getElementById("unitInit").value;
    unit.controlledBy = document.getElementById("unitControlledBy").value;
    unit.color = document.getElementById("unitColor").value;
    unit.type = document.getElementById("unitType").value;
    unit.HP = parseInt(document.getElementById("unitHP").value);
    unit.maxHP = unit.HP;
    socket.emit('add_unit', {addToInitiative: document.getElementById("addToInit").checked ,unit: unit, room: room, gmKey: gmKey});
    document.getElementById("unitName").value = "";
    document.getElementById("unitName").focus();
    document.getElementById("unitShortName").value = "";
    document.getElementById("unitInit").value = "";
}
function cssrules() {
    var rules = {};
    for (var i=0; i<document.styleSheets.length; ++i) {
        var cssRules = document.styleSheets[i].cssRules;
        for (var j=0; j<cssRules.length; ++j)
            rules[cssRules[j].selectorText] = cssRules[j];
    }
    return rules;
}

function css_getclass(name) {
    var rules = cssrules();
    if (!rules.hasOwnProperty(name))
        throw 'TODO: deal_with_notfound_case';
    return rules[name];
    }
function zoomIn() {
    lookingAtX = (document.getElementById("mapContainer").clientWidth/2 + document.getElementById("mapContainer").scrollLeft)/zoomSize
    lookingAtY = (document.getElementById("mapContainer").clientHeight/2 + document.getElementById("mapContainer").scrollTop)/zoomSize
    zoomSize *= 1.5;
    updateMap(gmData);
    document.getElementById("mapContainer").scrollLeft = lookingAtX*zoomSize - document.getElementById("mapContainer").clientWidth/2
    document.getElementById("mapContainer").scrollTop = lookingAtY*zoomSize - document.getElementById("mapContainer").clientHeight/2
}
function zoomOut() {
    lookingAtX = (document.getElementById("mapContainer").clientWidth/2 + document.getElementById("mapContainer").scrollLeft)/zoomSize
    lookingAtY = (document.getElementById("mapContainer").clientHeight/2 + document.getElementById("mapContainer").scrollTop)/zoomSize
    zoomSize /= 1.5;
    updateMap(gmData);
    document.getElementById("mapContainer").scrollLeft = lookingAtX*zoomSize - document.getElementById("mapContainer").clientWidth/2
    document.getElementById("mapContainer").scrollTop = lookingAtY*zoomSize - document.getElementById("mapContainer").clientHeight/2
}
function beginInit() {
    socket.emit('begin_init', {room: room, gmKey: gmKey});
}
function advanceInit() {
    socket.emit('advance_init', {room: room, gmKey: gmKey});
}
function endInit() {
    socket.emit('end_init', {room: room, gmKey: gmKey});
}
function saveEncounter() {
    socket.emit('save_encounter', {encounterName: document.getElementById("encounterName").value, room: room, gmKey: gmKey});
}
function loadEncounter() {
    socket.emit('load_encounter', {clearLocations: document.getElementById("clearLocations").checked, encounterName: document.getElementsByClassName("selectedEncounter")[0].id, room: room, gmKey: gmKey});
}
function clearMap() {
    socket.emit('clear_map', {clearLocations: document.getElementById("clearLocations").checked, room: room, gmKey: gmKey});
}

function removeEncounter(encounterName) {
    socket.emit('remove_encounter', {encounterName: encounterName, room: room, gmKey: gmKey});
}
function clickEncounter(ob) {
    tmpEncounters = document.getElementById("encountersDiv").children;
    for(var i = 0; i < tmpEncounters.length; i++){
        tmpEncounters[i].className = "";
    }
    ob.className = "selectedEncounter";
}
function removeInit(e, initCount) {
    e.stopPropagation();
    socket.emit('remove_init', {initCount: initCount, room: room, gmKey: gmKey});
}
function removeUnit(e, unitCount) {
    e.stopPropagation();
    socket.emit('remove_unit', {unitCount: unitCount, room: room, gmKey: gmKey});
}
function delInit(e, initCount) {
    e.stopPropagation();
    socket.emit('del_init', {initCount: initCount, room: room, gmKey: gmKey});
}

function mapClick(e, x, y) {
    console.log("Clicked!" + x + ", " + y);
    if (typeof selectedInitiative !== "undefined") {
        socket.emit('locate_unit', {selectedInit: selectedInitiative, moveType: document.getElementById("movementSelector").selectedIndex, xCoord: x, yCoord: y, room: room, gmKey: gmKey});
        return;
    } else if (typeof selectedUnits[0] !== "undefined" && !e.shiftKey) {
        console.log({selectedUnit: selectedUnits[0], xCoord: x, yCoord: y, room: room, gmKey: gmKey});
        socket.emit('locate_unit', {selectedUnit: selectedUnits[0], moveType: document.getElementById("movementSelector").selectedIndex, xCoord: x, yCoord: y, room: room, gmKey: gmKey});
        return;
    } else if (typeof selectedTool !== "undefined") {
        socket.emit('map_edit', {newTile: selectedTool.id, xCoord: x, yCoord: y, room: room, gmKey: gmKey});
        return
    } else {
        if (gmData.inInit && gmData.initiativeList[gmData.initiativeCount].controlledBy == "gm") {
            socket.emit('locate_unit', {selectedInit: gmData.initiativeCount, moveType: document.getElementById("movementSelector").selectedIndex, xCoord: x, yCoord: y, room: room, gmKey: gmKey});
            return
        }
    }
    if (!e.shiftKey) {
        deselectAll()
        populateEditChar(gmData,0);
    }
    for (i=0;i<gmData.unitList.length; i++) {
        if (typeof gmData.unitList[i].x !== "undefined" && gmData.unitList[i].x == x && gmData.unitList[i].y == y){
            document.getElementById("unitsDiv").children[i].children[0].className = "selected";
            selectedUnits.push(i);
            populateEditChar(gmData,i);
        }
    }
}

function changeHP(initnum) {
    socket.emit('change_hp', {changeHP: document.getElementById(`hpChange${initnum}`).value, room: room, gmKey: gmKey, initCount: initnum});
}

function deselectAll() {
    for(var i = 0; i < document.getElementById("initiativeDiv").children.length; i++){
        document.getElementById("initiativeDiv").children[i].children[0].className = "nonSelectedInit";
    }
    selectedInitiative = undefined;
    for(var i = 0; i < document.getElementById("unitsDiv").children.length; i++){
        document.getElementById("unitsDiv").children[i].children[0].className = "nonSelectedInit";
    }
    selectedUnits = [];
    for(var i = 0; i < document.getElementById("mapTools").children.length; i++){
        document.getElementById("mapTools").children[i].className = "nonSelected";
    }
    selectedTool = undefined;
}

function selectInitiative(initiativeNum) {
    if (typeof selectedInitiative !== "undefined") {
        if (initiativeNum == selectedInitiative) {
            document.getElementById("initiativeDiv").children[initiativeNum].children[0].className = "nonSelectedInit";
            selectedInitiative = undefined;
        } else {
            deselectAll();
            //document.getElementById("initiativeDiv").children[selectedInitiative].children[0].className = "nonSelectedInit";
            document.getElementById("initiativeDiv").children[initiativeNum].children[0].className = "selectedInit";
            selectedInitiative = initiativeNum;
        }
    } else {
        deselectAll();
        document.getElementById("initiativeDiv").children[initiativeNum].children[0].className = "selectedInit";
        selectedInitiative = initiativeNum;
    }
    if (typeof selectedInitiative !== "undefined") {
        populateEditChar(gmData, gmData.initiativeList[selectedInitiative].unitNum);
    } else {
        populateEditChar(gmData, 0);
    }
}
function selectUnit(e, unitNum) {
    if (selectedUnits.length == 0) {
        deselectAll();
        document.getElementById("unitsDiv").children[unitNum].children[0].className = "selected";
        selectedUnits = [unitNum];
    } else if (selectedUnits.includes(unitNum)) {
        document.getElementById("unitsDiv").children[unitNum].children[0].className = "nonSelected";
        selectedUnits.splice(selectedUnits.indexOf(unitNum), 1)
    } else if (e.shiftKey) {
        tmpUnits = selectedUnits;
        deselectAll()
        selectedUnits = tmpUnits
        selectedUnits.push(unitNum);
        for (i=0; i<selectedUnits.length;i++) {
            document.getElementById("unitsDiv").children[selectedUnits[i]].children[0].className = "selected";
        }
    } else {
        for (i = 0; i < selectedUnits.length; i++) {
            document.getElementById("unitsDiv").children[selectedUnits[i]].children[0].className = "nonSelected";
        }
        document.getElementById("unitsDiv").children[unitNum].children[0].className = "selected";
        selectedUnits = [unitNum];
    }
    if (typeof selectedUnits[0] !== "undefined") {
        populateEditChar(gmData, selectedUnits[0]);
    } else {
        populateEditChar(gmData, 0);
    }
}

function activeInitiative(initiativeNum) {
    document.getElementById("initiativeDiv").children[initiativeNum].children[1].style.display = "block";
}

function resetMovement() {
    socket.emit('reset_movement', {selectedInit: gmData.initiativeCount, room: room, gmKey: gmKey});
}
function addInit() {
    if (selectedUnits.length == 0) {return;}
    socket.emit('add_to_initiative', {selectedUnits: selectedUnits, room: room, gmKey: gmKey});
}
function earlierInit(e, ourInitNum) {
    e.stopPropagation();
    socket.emit('earlier_initiative', {targetInitiativeCount: ourInitNum, room: room, gmKey: gmKey});
}
function laterInit(e, ourInitNum) {
    e.stopPropagation();
    console.log(ourInitNum);
    socket.emit('later_initiative', {targetInitiativeCount: ourInitNum, room: room, gmKey: gmKey});
}
function updateChar () {
    player = {};
    player.room = room;
    player.gmKey = gmKey;
    player.unitNum = document.getElementById("editCharNum").innerText;
    player.charName = document.getElementById("charactername").innerText;
    player.charShortName = document.getElementById("charShortName").value;
    player.color = document.getElementById("playerColor").value;
    if (player.color == "custom") { player.color = document.getElementById("customColor").value;}
    player.perception = document.getElementById("perception").value;
    player.movementSpeed = document.getElementById("movementSpeed").value;
    player.dex = document.getElementById("dex").value;
    player.size = document.getElementById("size").value;
    player.darkvision = document.getElementById("darkvision").checked;
    player.lowLight = document.getElementById("lowLight").checked;
    player.trapfinding = document.getElementById("trapfinding").checked;
    player.revealsMap = document.getElementById("revealsMap").checked;
    player.hasted = document.getElementById("hasted").checked;
    player.permanentAbilities = document.getElementById("permanentAbilities").value;
    socket.emit('update_unit', player);
}
