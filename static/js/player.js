url_ob = new URL(window.location.href);
var room = url_ob.searchParams.get("room");
var socket;
var charName = "";
var zoomSize = 20;
var activeCharName = "";
var playerdata;
var socket;
var selectedUnit;
var selectedInitiative;
var lookingAtX;
var lookingAtY;
const isGM = false;
window.onload = function() {
    enableTab("mapWrapper")
    document.getElementById("updateCharButton").style.display = "none";
    socket = io.connect('http://' + document.domain + ':' + location.port, {'sync disconnect on unload': true, transports: ['websocket'], upgrade: false});
    // verify our websocket connection is established
    socket.on('connect', function() {
        console.log('Websocket connected!');
        if (url_ob.searchParams.get("charName")) {
            document.getElementById("charWrapper").appendChild( document.getElementById("charDiv"));
            document.getElementById("joinDiv").style.display = "none";
            document.getElementById("joinGameButton").style.display = "none";
            document.getElementById("updateCharButton").style.display = "block";
            document.getElementById("screenDiv").style.display = "block";
            console.log('sending join');
            charName=url_ob.searchParams.get("charName")
            socket.emit('player_join', {room: room, charName: charName});
            socket.emit("get_lore", room);
        }
    });
    socket.on('do_update', function(msg) {
        playerData = msg;
        console.log(playerData);
        document.title = playerData.name
        updateMap(playerData);
        if (playerData.inInit) {
            selectedUnit = undefined;
        } else {
            selectedInitiative = undefined;
        }

        if (typeof selectedUnit !== "undefined" && playerData.unitList[selectedUnit].controlledBy == charName) {
            populateEditChar(playerData, playerData.unitList[selectedUnit].unitNum)
        } else if (typeof selectedInitiative !== "undefined" && playerData.initiativeList[selectedInitiative].controlledBy == charName) {
            populateEditChar(playerData, playerData.initiativeList[selectiveInitiative].unitNum)
        } else {
            populateEditChar(playerData, playerData.playerList[charName].unitNum)
        }

        // populate initiative
        document.getElementById("initiativeDiv").innerHTML = "";
        document.getElementById("unitDiv").innerHTML = "";
        if (playerData.inInit) {
          if (playerData.initiativeList[playerData.initiativeCount].controlledBy == charName) {
              document.getElementById("movementDiv").style.display = "block";
              //document.getElementById("movement").style.display = "block";
          } else {
          document.getElementById("movementDiv").style.display = "none";
          }
          document.getElementById("initiativeDivContainer").style.display = "block";
          document.getElementById("unitDivContainer").style.display = "none";
          for (var i = 0; i < playerData.initiativeList.length; i++) {
              tmpHTML = `<div style="display:flex; height:40px;" onclick="selectInitiative(${i})">`
              if (typeof selectedInitiative !== "undefined" && i == selectedInitiative) {
                  tmpHTML += `<div class="selectedInit">`;
              } else {
                  tmpHTML += `<div class="nonSelectedInit">`;
              }
              tmpHTML += '<div style="float:left; padding:7px;">' + playerData.initiativeList[i].charName + '</div><div style="float:right;">' + playerData.initiativeList[i].initiative +
              '</div></div><div id="activeInit"><--</div></div>';
              document.getElementById("initiativeDiv").innerHTML += tmpHTML;

          }
          activeInitiative(playerData.initiativeCount)
          activeCharName = playerData.initiativeList[playerData.initiativeCount].charName;
          if (charName == activeCharName || charName == playerData.initiativeList[playerData.initiativeCount].controlledBy) {
              document.getElementById("advanceInit").style.display = "block";
          } else {
            document.getElementById("advanceInit").style.display = "none";
          }
        } else {
          document.getElementById("movementDiv").style.display = "none";
          //document.getElementById("movement").style.display = "none";
          document.getElementById("initiativeDivContainer").style.display = "none";
          document.getElementById("unitDivContainer").style.display = "block";
          for (var i = 0; i < playerData.unitList.length; i++) {
              tmpHTML = `<div style="display:flex; height:40px;" onclick="selectUnit(this, ${playerData.unitList[i].unitNum})"`
              if (typeof selectedUnit !== "undefined" && playerData.unitList[i].unitNum == selectedUnit) {
                  tmpHTML += `class="selected"><div>`;
              } else {
                  tmpHTML += `class="nonSelected"><div>`;
              }
              tmpHTML += '<div style="float:left; padding:7px;">' + playerData.unitList[i].charName + '</div></div></div>';
              document.getElementById("unitDiv").innerHTML += tmpHTML;
          }
        }

        //update player list
        document.getElementById("connectedPlayers").innerHTML = "";
        for (var i = 0; i < Object.keys(playerData.playerList).length; i++) {
          tmpPlayerName = Object.keys(playerData.playerList)[i];
          if (playerData.playerList[tmpPlayerName].connected) {
            document.getElementById("connectedPlayers").innerHTML += tmpPlayerName + "<br >";
          }
        }


        //handle request for init roll
        if (playerData.playerList[charName].requestInit && document.getElementById("promptDiv").innerHTML == "") {
            document.getElementById("activeTabDiv").style.height = "calc(70% - 40px)";
            document.getElementById("bottomDiv").style.display = "block";
            tmpHTML = '<form action="javascript:sendInit()">';
            for (i=0; i< playerData.unitList.length;i++) {
                if (playerData.unitList[i].controlledBy == charName) {
                    tmpHTML += '<div style="display: inline-block; padding:4px;">';
                    tmpHTML += playerData.unitList[i].charName + ': <br>';
                    tmpHTML += `<input type="text" id="init${i}">`;
                    tmpHTML += '</div>';
                }
            }
            tmpHTML += '</form>';
            tmpHTML += '<button onclick="sendInit()">Send Initiative</button>';
            document.getElementById("promptDiv").innerHTML = tmpHTML;
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
    socket.on("showLore", function(msg) {
        updateLore(msg.lore, msg.lore_num);
    });
} //end onload
window.onunload = function() {
    socket.emit('player_disconnect', {room: room, charName: charName});
    socket.close();
}
function advanceInit() {
    socket.emit('advance_init', {room: room, charName: charName});
}
function zoomIn() {
    lookingAtX = (document.getElementById("mapContainer").clientWidth/2 + document.getElementById("mapContainer").scrollLeft)/zoomSize
    lookingAtY = (document.getElementById("mapContainer").clientHeight/2 + document.getElementById("mapContainer").scrollTop)/zoomSize
    zoomSize *= 1.5;
    updateMap(playerData);
    document.getElementById("mapContainer").scrollLeft = lookingAtX*zoomSize - document.getElementById("mapContainer").clientWidth/2
    document.getElementById("mapContainer").scrollTop = lookingAtY*zoomSize - document.getElementById("mapContainer").clientHeight/2
}
function zoomOut() {
    lookingAtX = (document.getElementById("mapContainer").clientWidth/2 + document.getElementById("mapContainer").scrollLeft)/zoomSize
    lookingAtY = (document.getElementById("mapContainer").clientHeight/2 + document.getElementById("mapContainer").scrollTop)/zoomSize
    zoomSize /= 1.5;
    updateMap(playerData);
    document.getElementById("mapContainer").scrollLeft = lookingAtX*zoomSize - document.getElementById("mapContainer").clientWidth/2
    document.getElementById("mapContainer").scrollTop = lookingAtY*zoomSize - document.getElementById("mapContainer").clientHeight/2
}
function sendInit() {
    console.log('Sending...');
    console.log(room);
    tmpInit = [];
    for (i=0; i< playerData.unitList.length;i++) {
        if (playerData.unitList[i].controlledBy == charName) {
            if (Number.isNaN(parseInt(document.getElementById(`init${i}`).value))){
                return
            }
            tmpInit.push(document.getElementById(`init${i}`).value)
        }
    }
    document.getElementById("bottomDiv").style.display = "none";
    document.getElementById("activeTabDiv").style.height = "calc(100% - 40px)";
    document.getElementById("promptDiv").innerHTML = "";
    socket.emit('send_initiative', {initiative: tmpInit, charName: charName, room: room});
}
function mapClick(e, x, y) {
    console.log("Clicked!" + x + ", " + y);
    if (playerData.inInit) {
        socket.emit('locate_unit', {requestingPlayer: charName, moveType: document.getElementById("movementSelector").selectedIndex, selectedUnit: playerData.initiativeList[playerData.initiativeCount].unitNum, xCoord: x, yCoord: y, room: room});
    } else {
        if (typeof selectedInitiative === "undefined" && typeof selectedUnit === "undefined") {
            socket.emit('locate_unit', {requestingPlayer: charName, selectedUnit: playerData.playerList[charName].unitNum, xCoord: x, yCoord: y, room: room});
        } else if (typeof selectedInitiative !== "undefined") {
            socket.emit('locate_unit', {requestingPlayer: charName, selectedUnit: playerData.initiativeList[selectedInitiative].unitNum, xCoord: x, yCoord: y, room: room});
        } else if (typeof selectedUnit !== "undefined") {
            socket.emit('locate_unit', {requestingPlayer: charName, selectedUnit: selectedUnit, xCoord: x, yCoord: y, room: room});
        }
    }
}
function selectInitiative(initiativeNum) {
    if (typeof selectedInitiative !== "undefined") {
        if (initiativeNum == selectedInitiative) {
            document.getElementById("initiativeDiv").children[initiativeNum].children[0].className = "nonSelectedInit";
            selectedInitiative = undefined;
        } else {
            document.getElementById("initiativeDiv").children[selectedInitiative].children[0].className = "nonSelectedInit";
            document.getElementById("initiativeDiv").children[initiativeNum].children[0].className = "selectedInit";
            selectedInitiative = initiativeNum;
        }
    } else {
        document.getElementById("initiativeDiv").children[initiativeNum].children[0].className = "selectedInit";
        selectedInitiative = initiativeNum;
    }
    if (typeof selectedInitiative !== "undefined" && playerData.initiativeList[selectedInitiative].controlledBy == charName) {
        populateEditChar(playerData, playerData.initiativeList[selectedInitiative].unitNum);
    } else {
        populateEditChar(playerData, 0);
    }
}
function activeInitiative(initiativeNum) {
    document.getElementById("initiativeDiv").children[initiativeNum].children[1].style.display = "block";
}
function sendChat() {
    socket.emit('chat', {chat: document.getElementById('newChat').value, charName: charName, room: room});
    document.getElementById('newChat').value = "";
}

function joinGame() {

            document.getElementById("charWrapper").appendChild( document.getElementById("charDiv"));
            document.getElementById("joinGameButton").style.display = "none";
            document.getElementById("updateCharButton").style.display = "block";

    console.log({room: room, charName: charName});
    document.getElementById("joinDiv").style.display = "none";
    document.getElementById("screenDiv").style.display = "block";
    charName = document.getElementById("charName").value;
    charShortName = document.getElementById("charShortName").value;
    color = document.getElementById("playerColor").value;
    perception = document.getElementById("perception").value;
    movementSpeed = document.getElementById("movementSpeed").value;
    dex = document.getElementById("dex").value;
    size = document.getElementById("size").value;
    darkvision = document.getElementById("darkvision").checked;
    lowLight = document.getElementById("lowLight").checked;
    trapfinding = document.getElementById("trapfinding").checked;
    permanentAbilities = document.getElementById("permanentAbilities").value;
    window.history.replaceState(null, null, window.location.href + `&charName=${charName}`);
    socket.emit('player_join', {room: room, charName: charName, charShortName: charShortName, color: color, perception: perception, movementSpeed: movementSpeed, dex: dex, size: size, darkvision: darkvision, lowLight: lowLight, trapfinding: trapfinding, permanentAbilities: permanentAbilities});
    socket.emit("get_lore", room);
}
function selectUnit(e, selectedUnitNum) {
    if (typeof selectedUnit == "undefined") {
        e.className = "selected";
        selectedUnit = selectedUnitNum;
    } else {
        for (i=0; i<document.getElementById("unitDiv").children.length; i++) {
            document.getElementById("unitDiv").children[i].className = "nonSelected";
        }
        if (selectedUnit == selectedUnitNum) {
            selectedUnit = undefined;
        } else {
            e.className = "selected";
            selectedUnit = selectedUnitNum;
        }
    }
    if (typeof selectedUnit !== "undefined") {
        if (playerData.unitList[selectedUnit].controlledBy == charName) {populateEditChar(playerData, selectedUnit)}
    } else {
        populateEditChar(playerData, playerData.playerList[charName].unitNum)
    }
}
function addUnit() {
    var unit = {};
    unit.charName = document.getElementById("unitName").value;
    unit.charShortName = document.getElementById("unitShortName").value;
    unit.color = document.getElementById("unitColor").value;
    unit.type = document.getElementById("unitType").value;
    socket.emit('add_player_unit', {unit: unit, room: room, charName: charName});
    document.getElementById("unitName").value = "";
    document.getElementById("unitName").focus();
    document.getElementById("unitShortName").value = "";
}
function resetMovement() {
    socket.emit('reset_movement', {selectedInit: playerData.initiativeCount, room: room});
}
function updateChar () {
    player = {};
    player.room = room;
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
    player.hasted = document.getElementById("hasted").checked;
    player.lowLight = document.getElementById("lowLight").checked;
    player.trapfinding = document.getElementById("trapfinding").checked;
    player.permanentAbilities = document.getElementById("permanentAbilities").value;
    socket.emit('update_unit', player);
}
