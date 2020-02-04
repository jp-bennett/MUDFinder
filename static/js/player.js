url_ob = new URL(window.location.href);
var requestedUpdate = true;
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
                //document.getElementById("charWrapper").appendChild( document.getElementById("charDiv"));
                document.getElementById("charDiv").style.display = "none";
                document.getElementById("joinDiv").style.display = "none";
                document.getElementById("joinGameButton").style.display = "none";
                //document.getElementById("updateCharButton").style.display = "block";
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
            if (document.getElementById("charWrapper").style.display == "none") {
                populateSheet(playerData.playerList[charName]);
                /*if (typeof selectedUnit !== "undefined" && playerData.unitList[selectedUnit].controlledBy == charName) {
                    populateEditChar(playerData, playerData.unitList[selectedUnit].unitNum)
                } else if (typeof selectedInitiative !== "undefined" && playerData.initiativeList[selectedInitiative].controlledBy == charName) {
                    populateEditChar(playerData, playerData.initiativeList[selectedInitiative].unitNum)
                } else {
                    populateEditChar(playerData, playerData.playerList[charName].unitNum);
                    populateSkills(playerData.playerList[charName].skills);
                }*/
            } else {
                updateImages(playerData.playerList[charName])
                /*if (typeof selectedUnit !== "undefined" && playerData.unitList[selectedUnit].controlledBy == charName) {
                    updateImages(playerData.unitList[selectedUnit])
                } else if (typeof selectedInitiative !== "undefined" && playerData.initiativeList[selectedInitiative].controlledBy == charName) {
                    updateImages(playerData.initiativeList[selectedInitiative])
                } else {
                    updateImages(playerData.playerList[charName])
                }*/
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
        requestedUpdate = false;
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
        //charToken = document.getElementById("charToken").value;
        color = document.getElementById("playerColor").value;
        perception = document.getElementById("passivePerception").value;
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
        //player.charShortName = document.getElementById("charShortName").value;
        //player.token = document.getElementById("charToken").value;
        player.color = document.getElementById("playerColor").value;
        if (player.color == "custom") { player.color = document.getElementById("customColor").value;}
        player.perception = document.getElementById("perception").value;
        player.movementSpeed = document.getElementById("movementSpeed").value;
        player.dex = document.getElementById("dex").value;
        player.size = document.getElementById("size").value;
        player.darkvision = document.getElementById("darkvision").checked;
        //player.hasted = document.getElementById("hasted").checked;
        player.lowLight = document.getElementById("lowLight").checked;
        player.trapfinding = document.getElementById("trapfinding").checked;
        player.permanentAbilities = document.getElementById("permanentAbilities").value;
        socket.emit('update_unit', player);
    } catch (e) {
        socket.emit("error_handle", room, e);
    }
}

function updatePlayer () {
    try {
        player = {};
        player.room = room;
        player.charName = charName;
        player.alignment = document.getElementById("sheetAlignment").value;
        player.size = document.getElementById("sheetSize").value;
        player.height = document.getElementById("sheetHeight").value;
        player.weight = document.getElementById("sheetWeight").value;
        player.level = document.getElementById("sheetLevel").value;
        player.age = document.getElementById("sheetAge").value;
        player.deity = document.getElementById("sheetDeity").value;
        player.hair = document.getElementById("sheetHair").value;
        player.eyes = document.getElementById("sheetEyes").value;
        player.race = document.getElementById("sheetRace").value;
        player.gender = document.getElementById("sheetGender").value;
        player.homeland = document.getElementById("sheetHomeland").value;
        player.movementSpeed = document.getElementById("sheetMovementSpeed").value;
        player.armorSpeed = document.getElementById("sheetArmorSpeed").value;
        player.flySpeed = document.getElementById("sheetFlySpeed").value;
        player.flyManeuverability = document.getElementById("sheetFlyManeuverability").value;
        player.swimSpeed = document.getElementById("sheetSwimSpeed").value;
        player.climbSpeed = document.getElementById("sheetClimbSpeed").value;
        player.burrowSpeed = document.getElementById("sheetBurrowSpeed").value;


        player.STR = document.getElementById("sheetSTRScore").value
        player.DEX = document.getElementById("sheetDEXScore").value
        player.CON = document.getElementById("sheetCONScore").value
        player.INT = document.getElementById("sheetINTScore").value
        player.WIS = document.getElementById("sheetWISScore").value
        player.CHA = document.getElementById("sheetCHAScore").value

        player.HP = document.getElementById("sheetHP").value;
        player.maxHP = document.getElementById("sheetMaxHP").value;
        player.DR = document.getElementById("sheetDR").value;
        player.wounds = document.getElementById("sheetWounds").value;
        player.nonLethal = document.getElementById("sheetNonLethal").value;
        player.miscToInit = document.getElementById("sheetMiscToInit").value;
        player.BAB = document.getElementById("sheetBAB").value;
        player.ACArmor = document.getElementById("sheetACArmor").value;
        player.ACShield = document.getElementById("sheetACShield").value;
        player.ACNatural = document.getElementById("sheetACNatural").value;
        player.deflection = document.getElementById("sheetACDeflection").value;
        player.ACMisc = document.getElementById("sheetACMisc").value;

        player.fortBase = document.getElementById("sheetFortBase").value;
        player.fortMagic = document.getElementById("sheetFortMagic").value;
        player.fortMisc = document.getElementById("sheetFortMisc").value;
        player.reflexBase = document.getElementById("sheetReflexBase").value;
        player.reflexMagic = document.getElementById("sheetReflexMagic").value;
        player.reflexMisc = document.getElementById("sheetReflexMisc").value;
        player.willBase = document.getElementById("sheetWillBase").value;
        player.willMagic = document.getElementById("sheetWillMagic").value;
        player.willMisc = document.getElementById("sheetWillMisc").value;

        player.SR = document.getElementById("sheetSR").value;
        player.ER = document.getElementById("sheetER").value;
        player.weapons = [];
        player.weapons[0] = []
        player.weapons[0].push(document.getElementsByClassName("sheetWeaponName")[0].value);
        player.weapons[0].push(document.getElementsByClassName("sheetWeaponAttack")[0].value);
        player.weapons[0].push(document.getElementsByClassName("sheetWeaponDamage")[0].value);
        player.weapons[0].push(document.getElementsByClassName("sheetWeaponCrit")[0].value);
        player.weapons[0].push(document.getElementsByClassName("sheetWeaponType")[0].value);
        player.weapons[0].push(document.getElementsByClassName("sheetWeaponRange")[0].value);
        player.weapons[0].push(document.getElementsByClassName("sheetWeaponAmmo")[0].value);

        player.skills = getSkills();
        socket.emit('update_player', player);
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

function setSpeeds() {
    document.getElementById("sheetMovementSpeedSQ").value = document.getElementById("sheetMovementSpeed").value / 5 ;
    document.getElementById("sheetArmorSpeedSQ").value = document.getElementById("sheetArmorSpeed").value / 5 ;
}

function setSTRScore(score) {
    try {
        STRMod = Math.floor((score - 10) / 2);
        document.getElementById("sheetSTRMod").value = STRMod;
        strElements = document.getElementsByClassName("usesSTRMod");
        for (i=0, len=strElements.length; i<len; i=i+1) {
            strElements[i].value = STRMod;
            if (strElements[i].onchange !== null) {
                strElements[i].onchange()
            }
        }
    } catch (e) {
        socket.emit("error_handle", room, e);
    }
}

function setDEXScore(score) {
    try {
        DEXMod = Math.floor((score - 10) / 2);
        document.getElementById("sheetDEXMod").value = DEXMod;
        dexElements = document.getElementsByClassName("usesDEXMod");
        for (i=0, len=dexElements.length; i<len; i=i+1) {
            dexElements[i].value = DEXMod;
            if (dexElements[i].onchange !== null) {
                dexElements[i].onchange()
            }
        }
    } catch (e) {
        socket.emit("error_handle", room, e);
    }
}

function setCONScore(score) {
    try {
        CONMod = Math.floor((score - 10) / 2);
        document.getElementById("sheetCONMod").value = CONMod;
        conElements = document.getElementsByClassName("usesCONMod");
        for (i=0, len=conElements.length; i<len; i=i+1) {
            conElements[i].value = CONMod;
            if (conElements[i].onchange !== null) {
                conElements[i].onchange()
            }
        }
    } catch (e) {
        socket.emit("error_handle", room, e);
    }
}

function setINTScore(score) {
    try {
        INTMod = Math.floor((score - 10) / 2);
        document.getElementById("sheetINTMod").value = INTMod;

        intElements = document.getElementsByClassName("usesINTMod");
        for (i=0, len=intElements.length; i<len; i=i+1) {
            intElements[i].value = INTMod;
            if (intElements[i].onchange !== null) {
                intElements[i].onchange()
            }
        }
    } catch (e) {
        socket.emit("error_handle", room, e);
    }
}

function setWISScore(score) {
    try {
        WISMod = Math.floor((score - 10) / 2);
        document.getElementById("sheetWISMod").value = WISMod;
        wisElements = document.getElementsByClassName("usesWISMod");
        for (i=0, len=wisElements.length; i<len; i=i+1) {
            wisElements[i].value = WISMod;
            if (wisElements[i].onchange !== null) {
                wisElements[i].onchange()
            }
        }
    } catch (e) {
        socket.emit("error_handle", room, e);
    }
}

function setCHAScore(score) {
    try {
        CHAMod = Math.floor((score - 10) / 2);
        document.getElementById("sheetCHAMod").value = CHAMod;
        chaElements = document.getElementsByClassName("usesCHAMod");
        for (i=0, len=chaElements.length; i<len; i=i+1) {
            chaElements[i].value = CHAMod;
            if (chaElements[i].onchange !== null) {
                chaElements[i].onchange()
            }
        }
    } catch (e) {
        socket.emit("error_handle", room, e);
    }
}


function setInitBonus() {
    try {
        InitBonus = (parseInt(document.getElementById("sheetDEXToInit").value) || 0) + (parseInt(document.getElementById("sheetMiscToInit").value) || 0);
        document.getElementById("sheetInitBonus").value = InitBonus;
    } catch (e) {
        socket.emit("error_handle", room, e);
    }
}

function setAC() {
    try {
        AC = 10 + (parseInt(document.getElementById("sheetACArmor").value) || 0) +
        (parseInt(document.getElementById("sheetACShield").value) || 0) +
        (parseInt(document.getElementById("sheetACDEX").value) || 0) +
        (parseInt(document.getElementById("sheetACSize").value) || 0) +
        (parseInt(document.getElementById("sheetACNatural").value) || 0) +
        (parseInt(document.getElementById("sheetACDeflection").value) || 0) +
        (parseInt(document.getElementById("sheetACMisc").value) || 0);
        document.getElementById("sheetACTotal").value = AC;

        TouchAC = 10 +
        (parseInt(document.getElementById("sheetACDEX").value) || 0) +
        (parseInt(document.getElementById("sheetACSize").value) || 0) +
        (parseInt(document.getElementById("sheetACDeflection").value) || 0) +
        (parseInt(document.getElementById("sheetACMisc").value) || 0);
        document.getElementById("sheetTouchAC").value = TouchAC;

        FFAC = 10 + (parseInt(document.getElementById("sheetACArmor").value) || 0) +
        (parseInt(document.getElementById("sheetACShield").value) || 0) +
        (parseInt(document.getElementById("sheetACSize").value) || 0) +
        (parseInt(document.getElementById("sheetACNatural").value) || 0) +
        (parseInt(document.getElementById("sheetACDeflection").value) || 0) +
        (parseInt(document.getElementById("sheetACMisc").value) || 0);
        document.getElementById("sheetFFAC").value = FFAC;
    } catch (e) {
        socket.emit("error_handle", room, e);
    }
}

function setSaves() {
    try {
        fortSave = (parseInt(document.getElementById("sheetFortMod").value) || 0) +
            (parseInt(document.getElementById("sheetFortBase").value) || 0) +
            (parseInt(document.getElementById("sheetFortMagic").value) || 0) +
            (parseInt(document.getElementById("sheetFortMisc").value) || 0);
        document.getElementById("sheetFortTotal").value = fortSave;

        reflexSave = (parseInt(document.getElementById("sheetReflexMod").value) || 0) +
            (parseInt(document.getElementById("sheetReflexBase").value) || 0) +
            (parseInt(document.getElementById("sheetReflexMagic").value) || 0) +
            (parseInt(document.getElementById("sheetReflexMisc").value) || 0);
        document.getElementById("sheetReflexTotal").value = reflexSave;

        willSave = (parseInt(document.getElementById("sheetWillMod").value) || 0) +
            (parseInt(document.getElementById("sheetWillBase").value) || 0) +
            (parseInt(document.getElementById("sheetWillMagic").value) || 0) +
            (parseInt(document.getElementById("sheetWillMisc").value) || 0);
        document.getElementById("sheetWillTotal").value = willSave;
    } catch (e) {
        socket.emit("error_handle", room, e);
    }
}

function setBAB() {
    try {
        BAB = (parseInt(document.getElementById("sheetBAB").value) || 0);
        document.getElementById("sheetCMBBAB").value = BAB;
        if (document.getElementById("sheetCMBBAB").onchange !== null) {
            document.getElementById("sheetCMBBAB").onchange()
        }
        document.getElementById("sheetCMDBAB").value = BAB;
        if (document.getElementById("sheetCMDBAB").onchange !== null) {
            document.getElementById("sheetCMDBAB").onchange()
        }
    } catch (e) {
        socket.emit("error_handle", room, e);
    }
}

function setCMX() {
    try {
        CMB = (parseInt(document.getElementById("sheetCMBBAB").value) || 0) +
            (parseInt(document.getElementById("sheetCMBSTR").value) || 0) +
            (parseInt(document.getElementById("sheetCMBSize").value) || 0) +
            (parseInt(document.getElementById("sheetCMBMisc").value) || 0);
        document.getElementById("sheetCMBTotal").value = CMB;

        CMD = 10 + (parseInt(document.getElementById("sheetCMDBAB").value) || 0) +
            (parseInt(document.getElementById("sheetCMDSTR").value) || 0) +
            (parseInt(document.getElementById("sheetCMDDEX").value) || 0) +
            (parseInt(document.getElementById("sheetCMDSize").value) || 0) +
            (parseInt(document.getElementById("sheetCMDDeflection").value) || 0) +
            (parseInt(document.getElementById("sheetCMDMisc").value) || 0);
        document.getElementById("sheetCMDTotal").value = CMD;
    } catch (e) {
        socket.emit("error_handle", room, e);
    }
}

function convertSkill(skillName, newMod){
    //A feat/trait can call this with window["convertSkill"]
    //Should be the basis for giving feats the ability to do stuff without terribly hard-coding everything.
}

function calcSkill(skillName) {
    try {
        ourDiv = document.getElementById(skillName);
        skillBonus = (parseInt(ourDiv.children[3].value) || 0) +
        (parseInt(ourDiv.children[5].value) || 0) +
        (parseInt(ourDiv.children[7].value) || 0) +
        (parseInt(ourDiv.children[9].value) || 0) +
        (parseInt(ourDiv.children[11].value) || 0);
        if (ourDiv.children[13]) {
            skillBonus -= (parseInt(ourDiv.children[13].value) || 0);
        }
        if (ourDiv.children[6].checked && ((parseInt(ourDiv.children[5].value) || 0) > 0)) {
            skillBonus += 3;
        }
        ourDiv.children[1].value = skillBonus;
    } catch (e) {
        socket.emit("error_handle", room, e);
    }
}

function getSkills() {
    try{
        var skillsData = {};
        skillsDiv = document.getElementById("skillsDiv");
        skillsElements = skillsDiv.children;
        for (i=2, len=skillsElements.length; i<len; i=i+1) {
            var datas = [skillsElements[i].children[1].value, skillsElements[i].children[3].value, skillsElements[i].children[5].value, skillsElements[i].children[6].checked,
            skillsElements[i].children[7].value, skillsElements[i].children[9].value, skillsElements[i].children[11].value];
            if (skillsElements[i].children[13]) {
                datas.push(skillsElements[i].children[13].value)
            }
            skillsData[skillsElements[i].id] = datas;
        }
        return skillsData;
    } catch (e) {
        socket.emit("error_handle", room, e);
    }

}

function populateSkills(skillsData) {
    try{
        skillsDiv = document.getElementById("skillsDiv");
        skillsElements = skillsDiv.children;
        for (i=2, len=skillsElements.length; i<len; i=i+1) {
            skillsElements[i].children[1].value = skillsData[skillsElements[i].id][0];
            skillsElements[i].children[3].value = skillsData[skillsElements[i].id][1];
            skillsElements[i].children[5].value = skillsData[skillsElements[i].id][2];
            skillsElements[i].children[6].checked = skillsData[skillsElements[i].id][3];
            skillsElements[i].children[7].value = skillsData[skillsElements[i].id][4];
            skillsElements[i].children[9].value = skillsData[skillsElements[i].id][5];
            skillsElements[i].children[11].value = skillsData[skillsElements[i].id][6];
            if (skillsElements[i].children[13]) {
                skillsElements[i].children[13].value = skillsData[skillsElements[i].id][7];
            }
        }
        return;
    } catch (e) {
        socket.emit("error_handle", room, e);
    }

}

function populateSheet (data) {
    try {
        populateSkills(data.skills);
        updateImages(data);
        document.getElementById("sheetCharName").value = data.charName;
        document.getElementById("sheetAlignment").value = data.alignment;
        document.getElementById("sheetSize").value = data.size;
        document.getElementById("sheetSize").onchange();
        document.getElementById("sheetHeight").value = data.height;
        document.getElementById("sheetWeight").value = data.weight;
        document.getElementById("sheetLevel").value = data.level;
        document.getElementById("sheetAge").value = data.age;
        document.getElementById("sheetDeity").value = data.deity;
        document.getElementById("sheetHair").value = data.hair;
        document.getElementById("sheetEyes").value = data.eyes;
        document.getElementById("sheetRace").value = data.race;
        document.getElementById("sheetGender").value = data.gender;
        document.getElementById("sheetHomeland").value = data.homeland;

        document.getElementById("sheetMovementSpeed").value = data.movementSpeed;
        document.getElementById("sheetArmorSpeed").value = data.armorSpeed;
        document.getElementById("sheetMovementSpeed").onchange();
        document.getElementById("sheetFlySpeed").value = data.flySpeed;
        document.getElementById("sheetFlyManeuverability").value = data.flyManeuverability;
        document.getElementById("sheetSwimSpeed").value = data.swimSpeed;
        document.getElementById("sheetClimbSpeed").value = data.climbSpeed;
        document.getElementById("sheetBurrowSpeed").value = data.burrowSpeed;

        document.getElementById("sheetSTRScore").value = data.STR;
        if (!isNaN(parseInt(data.STR))) {
            setSTRScore(data.STR);
        }
        document.getElementById("sheetDEXScore").value = data.DEX;
        if (!isNaN(parseInt(data.DEX))) {
        setDEXScore(data.DEX);
        }
        document.getElementById("sheetCONScore").value = data.CON;
        if (!isNaN(parseInt(data.CON))) {
        setCONScore(data.CON);
        }
        document.getElementById("sheetINTScore").value = data.INT;
        if (!isNaN(parseInt(data.INT))) {
        setINTScore(data.INT);
        }
        document.getElementById("sheetWISScore").value = data.WIS;
        if (!isNaN(parseInt(data.WIS))) {
        setWISScore(data.WIS);
        }
        document.getElementById("sheetCHAScore").value = data.CHA;
        if (!isNaN(parseInt(data.CHA))) {
        setCHAScore(data.CHA);
        }



        document.getElementById("sheetHP").value = data.HP;
        document.getElementById("sheetMaxHP").value = data.maxHP;
        document.getElementById("sheetDR").value = data.DR;
        document.getElementById("sheetWounds").value = data.wounds;
        document.getElementById("sheetNonLethal").value = data.nonLethal;
        document.getElementById("sheetMiscToInit").value = data.miscToInit;
        document.getElementById("sheetMiscToInit").onchange();

        document.getElementById("sheetACArmor").value = data.ACArmor;
        document.getElementById("sheetACShield").value = data.ACShield;
        document.getElementById("sheetACNatural").value = data.ACNatural;
        document.getElementById("sheetACDeflection").value = data.deflection;
        document.getElementById("sheetACMisc").value = data.ACMisc;
        document.getElementById("sheetACMisc").onchange();



        document.getElementById("sheetCMDDeflection").value = data.deflection;

        document.getElementById("sheetFortBase").value = data.fortBase;
        document.getElementById("sheetFortMagic").value = data.fortMagic;
        document.getElementById("sheetFortMisc").value = data.fortMisc;
        document.getElementById("sheetReflexBase").value = data.reflexBase;
        document.getElementById("sheetReflexMagic").value = data.reflexMagic;
        document.getElementById("sheetReflexMisc").value = data.reflexMisc;
        document.getElementById("sheetWillBase").value = data.willBase;
        document.getElementById("sheetWillMagic").value = data.willMagic;
        document.getElementById("sheetWillMisc").value = data.willMisc;
        setSaves();

        document.getElementById("sheetSR").value = data.SR;
        document.getElementById("sheetER").value = data.ER;


        document.getElementById("sheetBAB").value = data.BAB;
        document.getElementById("sheetBAB").onchange();
        if (typeof data.weapons[0] !== "undefined") {
            document.getElementsByClassName("sheetWeaponName")[0].value = data.weapons[0][0]
            document.getElementsByClassName("sheetWeaponAttack")[0].value = data.weapons[0][1]
            document.getElementsByClassName("sheetWeaponDamage")[0].value = data.weapons[0][2]
            document.getElementsByClassName("sheetWeaponCrit")[0].value = data.weapons[0][3]
            document.getElementsByClassName("sheetWeaponType")[0].value = data.weapons[0][4]
            document.getElementsByClassName("sheetWeaponRange")[0].value = data.weapons[0][5]
            document.getElementsByClassName("sheetWeaponAmmo")[0].value = data.weapons[0][6]
        }

    } catch (e) {
        socket.emit("error_handle", room, e);
    }
}

function sizeUpdate() {
    size = document.getElementById("sheetSize").value;
    switch(size) {
        case "tiny":
            document.getElementById("sheetACSize").value = "2";
            document.getElementById("sheetCMBSize").value = "-2";
            document.getElementById("sheetCMDSize").value = "-2";
            break;
        case "small":
            document.getElementById("sheetACSize").value = "1";
            document.getElementById("sheetCMBSize").value = "-1";
            document.getElementById("sheetCMDSize").value = "-1";
            break;
        case "medium":
            document.getElementById("sheetACSize").value = 0;
            document.getElementById("sheetCMBSize").value = "0";
            document.getElementById("sheetCMDSize").value = "0";
            break;
        case "large":
            document.getElementById("sheetACSize").value = "-1";
            document.getElementById("sheetCMBSize").value = "1";
            document.getElementById("sheetCMDSize").value = "1";
            break;
        case "huge":
            document.getElementById("sheetACSize").value = "-2";
            document.getElementById("sheetCMBSize").value = "2";
            document.getElementById("sheetCMDSize").value = "2";
            break;
    }


}