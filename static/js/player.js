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
var gpTableSavedHTML;
var inventoryTableSavedHTML;
var selectedInventory;
var savedInventories;
const isGM = false;
window.onload = function() {
    try {
        gpTableSavedHTML = document.getElementById("gpTable").innerHTML;
        inventoryTableSavedHTML = document.getElementById("itemTable").innerHTML;
        enableTab("mapWrapper")
        document.getElementById("updateCharButton").style.display = "none";
    } catch (error) {
        alert ("Page initialization failed: " + error);
    }
    try {
        socket = io.connect(document.domain + ':' + location.port, {'sync disconnect on unload': true, transports: ['websocket'], upgrade: false});
    } catch (error) {
        alert("Could not connect to websocket: " + error);
    }

    socket.on('connect', function() {
        try {
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
                socket.emit("get_inventories", room, charName);
                selectedInventory = charName;
            }
        } catch (e) {
            socket.emit("error_handle", room, e);
        }
    });

    socket.on('reconnect', function () {
        try {
            console.log('you have been reconnected');
            // where username is a global variable for the client
            socket.emit('player_reconnect', room, charName);
        } catch (e) {
            socket.emit("error_handle", room, e);
        }
    });

    socket.on('do_update', function(msg) {
        try {
            playerData = msg;
            console.log(playerData);
            document.title = playerData.name
            updateMap(playerData);
            if (playerData.inInit) {
                selectedUnit = undefined;
            } else {
                selectedInitiative = undefined;
            }
            if (document.getElementById("charWrapper").style.display == "none"){
                if (typeof selectedUnit !== "undefined" && playerData.unitList[selectedUnit].controlledBy == charName) {
                    populateEditChar(playerData, playerData.unitList[selectedUnit].unitNum)
                } else if (typeof selectedInitiative !== "undefined" && playerData.initiativeList[selectedInitiative].controlledBy == charName) {
                    populateEditChar(playerData, playerData.initiativeList[selectedInitiative].unitNum)
                } else {
                    populateEditChar(playerData, playerData.playerList[charName].unitNum)
                }
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
                  '</div></div><div id="activeInit"><-</div></div>';
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
                    if (playerData.unitList[i].controlledBy == charName && !playerData.unitList[i].inInit) {
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
        } catch (e) {
            socket.emit("error_handle", room, e);
        }
    });

    socket.on('chat', function(msg) {
        try {
            console.log(msg);
            now = new Date;
            document.getElementById("chatText").innerText += "[" + now.getHours().toString().padStart(2, '0') + ":" + now.getMinutes().toString().padStart(2, '0') +
            ":" + now.getSeconds().toString().padStart(2, '0') + "] " + msg["charName"] + ": " + msg["chat"];
            document.getElementById("chatText").innerHTML += "<br />";
            document.getElementById("chatText").scrollTop = document.getElementById("chatText").scrollHeight;
        } catch (e) {
            socket.emit("error_handle", room, e);
        }
    });

    socket.on("showLore", function(msg) {
        try {
            updateLore(msg.lore, msg.lore_num);
        } catch (e) {
            socket.emit("error_handle", room, e);
        }
    });

    socket.on("update_inventory", populateInventory);

} //end onload
window.onunload = function() {
    socket.emit('player_disconnect', {room: room, charName: charName});
    socket.close();
}

function updateInv(element, invNum) {
    try {
        itemObj = {}
        itemObj.invNum = invNum;
        itemObj.isWorn = element.parentElement.parentElement.children[2].children[0].checked
        itemObj.itemWeight = element.parentElement.parentElement.children[3].children[0].value
        itemObj.itemValue = element.parentElement.parentElement.children[4].children[0].value
        itemObj.itemCount = element.parentElement.parentElement.children[5].children[0].value
        console.log(invNum)
        socket.emit('update_item', room, charName, selectedInventory, itemObj);
    } catch (e) {
        socket.emit("error_handle", room, e);
    }
}

function deleteItem(invNum) {
    socket.emit('delete_item', room, charName, selectedInventory, invNum);
}

function advanceInit() {
    socket.emit('advance_init', {room: room, charName: charName});
}

function zoomIn() {
    try {
        lookingAtX = (document.getElementById("mapContainer").clientWidth/2 + document.getElementById("mapContainer").scrollLeft)/zoomSize
        lookingAtY = (document.getElementById("mapContainer").clientHeight/2 + document.getElementById("mapContainer").scrollTop)/zoomSize
        zoomSize *= 1.5;
        updateMap(playerData);
        document.getElementById("mapContainer").scrollLeft = lookingAtX*zoomSize - document.getElementById("mapContainer").clientWidth/2
        document.getElementById("mapContainer").scrollTop = lookingAtY*zoomSize - document.getElementById("mapContainer").clientHeight/2
    } catch (e) {
        socket.emit("error_handle", room, e);
    }
}

function zoomOut() {
    try {
        lookingAtX = (document.getElementById("mapContainer").clientWidth/2 + document.getElementById("mapContainer").scrollLeft)/zoomSize
        lookingAtY = (document.getElementById("mapContainer").clientHeight/2 + document.getElementById("mapContainer").scrollTop)/zoomSize
        zoomSize /= 1.5;
        updateMap(playerData);
        document.getElementById("mapContainer").scrollLeft = lookingAtX*zoomSize - document.getElementById("mapContainer").clientWidth/2
        document.getElementById("mapContainer").scrollTop = lookingAtY*zoomSize - document.getElementById("mapContainer").clientHeight/2
    } catch (e) {
        socket.emit("error_handle", room, e);
    }
}
function sendInit() {
        try {
        console.log('Sending...');
        console.log(room);
        tmpInit = [];
        for (i=0; i< playerData.unitList.length;i++) {
            if (playerData.unitList[i].controlledBy == charName && !playerData.unitList[i].inInit) {
                if (Number.isNaN(parseInt(document.getElementById(`init${i}`).value)) && document.getElementById(`init${i}`).value !== ""){
                    return
                }
                tmpInit.push(document.getElementById(`init${i}`).value)
            }
        }
        document.getElementById("bottomDiv").style.display = "none";
        document.getElementById("activeTabDiv").style.height = "calc(100% - 40px)";
        document.getElementById("promptDiv").innerHTML = "";
        socket.emit('send_initiative', {initiative: tmpInit, charName: charName, room: room});
    } catch (e) {
        socket.emit("error_handle", room, e);
    }
}
function mapClick(e, x, y) {
    try {
        console.log("Clicked!" + x + ", " + y);
        relative_y = e.offsetX * 16 / zoomSize;
        relative_x = e.offsetY * 16 / zoomSize;
        console.log(relative_x + ", " + relative_y);

        if (playerData.inInit) {
            socket.emit('locate_unit', {requestingPlayer: charName, moveType: document.getElementById("movementSelector").selectedIndex, selectedUnit: playerData.initiativeList[playerData.initiativeCount].unitNum, xCoord: x, yCoord: y, relative_x: relative_x, relative_y: relative_y, room: room});
        } else {
            if (typeof selectedInitiative === "undefined" && typeof selectedUnit === "undefined") {
                socket.emit('locate_unit', {requestingPlayer: charName, selectedUnit: playerData.playerList[charName].unitNum, xCoord: x, yCoord: y, relative_x: relative_x, relative_y: relative_y, room: room});
            } else if (typeof selectedInitiative !== "undefined") {
                socket.emit('locate_unit', {requestingPlayer: charName, selectedUnit: playerData.initiativeList[selectedInitiative].unitNum, xCoord: x, relative_x: relative_x, relative_y: relative_y, yCoord: y, room: room});
            } else if (typeof selectedUnit !== "undefined") {
                socket.emit('locate_unit', {requestingPlayer: charName, selectedUnit: selectedUnit, xCoord: x, yCoord: y, relative_x: relative_x, relative_y: relative_y, room: room});
            }
        }
    } catch (error) {
        socket.emit("error_handle", room, error);
    }
}
function selectInitiative(initiativeNum) {
    try {
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
    } catch (e) {
        socket.emit("error_handle", room, e);
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
    try {
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
        selectedInventory = charName;
        socket.emit("get_inventories", room, charName);
    } catch (e) {
        socket.emit("error_handle", room, e);
    }
}


function selectUnit(e, selectedUnitNum) {
    try {
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
    } catch (error) {
        socket.emit("error_handle", room, error);
    }
}
function addUnit() {
    try {
        var unit = {};
        unit.charName = document.getElementById("unitName").value;
        unit.charShortName = document.getElementById("unitShortName").value;
        unit.color = document.getElementById("unitColor").value;
        unit.type = document.getElementById("unitType").value;
        unit.movementSpeed = document.getElementById("unitSpeed").value;
        socket.emit('add_player_unit', {unit: unit, room: room, charName: charName});
        document.getElementById("unitName").value = "";
        document.getElementById("unitName").focus();
        document.getElementById("unitShortName").value = "";
        document.getElementById("unitSpeed").value = "";
    } catch (e) {
        socket.emit("error_handle", room, e);
    }

}
function resetMovement() {
    socket.emit('reset_movement', {selectedInit: playerData.initiativeCount, room: room});
}
function updateChar () {
    try {
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
    } catch (e) {
        socket.emit("error_handle", room, e);
    }
}

function recordGP() {
    try {
        description = document.getElementById("gpDescription").value;
        increment = Number(document.getElementById("gpIncrement").value);
        decrement = Number(document.getElementById("gpDecrement").value);
        socket.emit("add_gp", room, charName, selectedInventory, description, increment, decrement);
    } catch (e) {
        socket.emit("error_handle", room, e);
    }
}

function deleteLastGPTransaction() {
socket.emit("delete_gp_transaction", room, charName, selectedInventory);
}

function recordItem() {
    try {
        itemObj = {}
        itemObj.item = document.getElementById("itemText").value;
        itemObj.itemSlot = document.getElementById("itemSlot").value;
        itemObj.isWorn = document.getElementById("isWorn").checked;
        itemObj.itemWeight = document.getElementById("itemWeight").value;
        itemObj.itemValue = document.getElementById("itemValue").value;
        itemObj.itemCount = document.getElementById("itemCount").value;
        socket.emit("add_item", room, charName, selectedInventory, itemObj)
    } catch (e) {
        socket.emit("error_handle", room, e);
    }
}

function changeInventory(newInventory) {
    try {
        selectedInventory = newInventory;
        if (selectedInventory == "add") {
            document.getElementById("addInv").style.display="block";
            document.getElementById("register").style.display="none";
            document.getElementById("items").style.display="none";
        } else {
            populateInventory(savedInventories);
        }
    } catch (e) {
        socket.emit("error_handle", room, e);
    }
}

function populateInventory(inventories) {
    try {
        document.getElementById("addInv").style.display="none";
        document.getElementById("register").style.display="block";
        document.getElementById("items").style.display="block";
        document.getElementById("inventoryTitle").innerText = selectedInventory;
        if (selectedInventory !== Object.keys(inventories)[0]) {
            document.getElementById("inventoryTitle").innerHTML += `<br><button onclick="deleteInventory('${selectedInventory}')">delete</button>`
        }
        savedInventories = inventories;
        tmpInventory = inventories[selectedInventory].gp;
        console.log(inventories[charName]);
        var table = document.getElementById("gpTable");
        table.innerHTML = gpTableSavedHTML;
        for (x=0;x<tmpInventory.length;x++){
            var row = table.insertRow(x+1);
            var descriptionCell = row.insertCell(0);
            var decrementCell = row.insertCell(1);
            var incrementCell = row.insertCell(2);
            var totalCell = row.insertCell(3);
            descriptionCell.innerText = tmpInventory[x].description
            decrementCell.innerText = tmpInventory[x].decrement
            incrementCell.innerText = tmpInventory[x].increment
            totalCell.innerText = tmpInventory[x].result
            if (x == tmpInventory.length-1){
                row.insertCell(4).innerHTML = '<button onclick="deleteLastGPTransaction()">Delete</button>';
            }
        }
        document.getElementById("register").scrollTop = document.getElementById("register").scrollHeight
        tmpInventory = inventories[selectedInventory].inventory;
        var table = document.getElementById("itemTable");
        table.innerHTML = inventoryTableSavedHTML;
        tmpWeight = 0;
        for (x=0;x<tmpInventory.length;x++){
            var row = table.insertRow(x+1);
            row.insertCell(0).innerText = tmpInventory[x].item;
            row.insertCell(1).innerText = tmpInventory[x].itemSlot;
            row.insertCell(2).innerHTML = `<input type="checkbox" ${(tmpInventory[x].isWorn) ? "checked" : ""}>`;
            row.insertCell(3).innerHTML = '<input type="text" style="width:40px;" value="' + tmpInventory[x].itemWeight + '"></input>';
            row.insertCell(4).innerHTML = '<input type="text" style="width:40px;" value="' + tmpInventory[x].itemValue + '"></input>';
            row.insertCell(5).innerHTML = '<input type="text" style="width:40px;" value="' + tmpInventory[x].itemCount + '"></input>';
            row.insertCell(6).innerHTML = `<button onclick="updateInv(this, ${x})">Update</button><button onclick="deleteItem( ${x})">Delete</button>`;
            if (!isNaN(tmpInventory[x].itemWeight) && !isNaN(tmpInventory[x].itemCount)) {
                tmpWeight += Number(tmpInventory[x].itemWeight) * Number(tmpInventory[x].itemCount);
            }
        }
        document.getElementById("totalWeight").innerHTML = "Total Weight: " + tmpWeight;
        tmpHTML = '';
        for (x=0;x<Object.keys(inventories).length; x++) {
            tmpName = Object.keys(inventories)[x];
            tmpHTML += `<div class="tab" onClick="changeInventory('${tmpName}')">${tmpName}</div>`;
        }
        tmpHTML += `<div class="tab" onClick="changeInventory('add')">add</div>`;
        document.getElementById("inventoryTabs").innerHTML = tmpHTML;
    } catch (e) {
        socket.emit("error_handle", room, e);
    }
}

function newInventory() {
    try {
        tmpSelectedInventory = document.getElementById("newInventoryName").value;
        if (typeof savedInventories[tmpSelectedInventory] == "undefined") {
        selectedInventory = tmpSelectedInventory;
        socket.emit("add_inventory", room, charName, selectedInventory)
        }
    } catch (e) {
        socket.emit("error_handle", room, e);
    }
}

function deleteInventory(invToDel) {
    try {
        if (invToDel !== Object.keys(savedInventories)[0]) {
            selectedInventory = Object.keys(savedInventories)[0]
            socket.emit("del_inventory", room, charName, invToDel)
        }
    } catch (e) {
        socket.emit("error_handle", room, e);
    }
}