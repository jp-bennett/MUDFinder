url_ob = new URL(window.location.href);
var requestedUpdate = true;
var room = url_ob.searchParams.get("room");
var socket;
var charName = "";
var zoomSize = 70;
var activeCharName = "";
var playerdata;
var socket;
var selectedUnits = [];
//var selectedInitiative;
var lookingAtX;
var lookingAtY;
var gpTableSavedHTML;
var inventoryTableSavedHTML;
var selectedInventory;
var savedInventories;
var spellcasting;
var savedSpellList;
var spellSelectionDestination = ["", 0, 0];
var effects;
const isGM = false;
window.addEventListener("resize", hackSizes);
window.onload = function() {
    try {
        gpTableSavedHTML = document.getElementById("gpTable").innerHTML;
        inventoryTableSavedHTML = document.getElementById("itemTable").innerHTML;
        enableTab("mapWrapper");

        document.getElementById("mapContainer").onwheel = function(e){
            try {
            e.preventDefault()
            e.stopPropagation();
            mouseX = (e.clientX)// / zoomSize;
            mouseX -= document.getElementById("mapContainer").getBoundingClientRect().x
            mouseXonDiv = mouseX;
            mouseX += document.getElementById("mapContainer").scrollLeft;
            oldZoom = zoom;
            mouseY = (e.clientY)// / zoomSize;
            mouseY -= document.getElementById("mapContainer").getBoundingClientRect().y
            mouseYonDiv = mouseY;
            mouseY += document.getElementById("mapContainer").scrollTop;
            YHidden = mouseY - mouseYonDiv
            XHidden = mouseX - mouseXonDiv

            if (e.deltaY < 0) {
                zoom *= 1.1; //add max zoom
                //zoomIn(mouseX, mouseY);
            } else if (e.deltaY > 0) {
                zoom /= 1.1 //add min zoom
                //zoomOut(mouseX, mouseY);
            }
            document.getElementById("mapGraphic").style.transform = `scale(${zoom})`;
            newMouseXfromPoint = mouseXonDiv / oldZoom * zoom;
            newMouseYfromPoint = mouseYonDiv / oldZoom * zoom;
            newYHidden = YHidden / oldZoom * zoom;
            newXHidden = XHidden / oldZoom * zoom;

            document.getElementById("mapContainer").scrollLeft = newXHidden + newMouseXfromPoint - mouseXonDiv;
            document.getElementById("mapContainer").scrollTop = newYHidden + newMouseYfromPoint - mouseYonDiv;

            } catch (e) {
                socket.emit("error_handle", room, e);
            }
        }


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
                document.getElementById("joinDiv").style.display = "none";
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
    socket.on('draw_map', function(msg) {
        drawMap(msg);
        mapObject = msg;
    });
    socket.on('player_map_update', function(msg) {
        updateMap(msg, mapObject);
    });
    socket.on('do_update', function(msg) {
        try {
            playerData = undefined;
            playerData = msg;
            unitsByUUID = {};
            for (var i = 0; i < msg.unitList.length; i++) {
                unitsByUUID[msg.unitList[i].uuid] = msg.unitList[i];
            }
            effects = playerData.effects;
            document.title = playerData.name
            drawUnits(playerData);
            if ((document.getElementById("charWrapper").style.display == "none") | requestedUpdate) { //tracking requestedUpdate may be all that's needed
                populateSheet(playerData.playerList[charName]);
            } else {
                updateImages(playerData.playerList[charName])
            }
            // populate initiative
            document.getElementById("initiativeDiv").innerHTML = "";
            document.getElementById("unitsDiv").innerHTML = "";
            if (playerData.inInit) {
                inInit = true;
                currentRound = playerData.roundCount;
                currentInit = playerData.initiativeCount;
              if (playerData.initiativeList[playerData.initiativeCount].controlledBy == charName) {
                  showBottomDiv();
                  document.getElementById("movementDiv").style.display = "block";
              } else {
                document.getElementById("movementDiv").style.display = "none";
              }
              document.getElementById("initiativeDivContainer").style.display = "block";
              document.getElementById("unitDivContainer").style.display = "none";
              for (var i = 0; i < playerData.initiativeList.length; i++) {
                  tmpHTML = `<div style="display:flex; height:40px;" onclick="selectInitiative(${i})">`
                  tmpHTML += `<div class="InitEntry">`;
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
                inInit = false;
                currentRound = -1;
                currentInit = -1;
              document.getElementById("movementDiv").style.display = "none";
              document.getElementById("initiativeDivContainer").style.display = "none";
              document.getElementById("unitDivContainer").style.display = "block";
              for (var i = 0; i < playerData.unitList.length; i++) {
                  tmpHTML = `<div style="display:flex; height:40px;" onclick="selectUnit(this, ${i})"`
                  tmpHTML += `class="unitListEntry"><div>`;
                  tmpHTML += '<div style="float:left; padding:7px;">' + playerData.unitList[i].charName + '</div></div></div>';
                  document.getElementById("unitsDiv").innerHTML += tmpHTML;
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
                document.getElementById("promptDiv").style.display = "block";
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
    socket.on("reloadLore", function(msg) {
        try {
            loreImages = new Array();
            updateLore(msg.lore, msg.lore_num);
        } catch (e) {
            socket.emit("error_handle", room, e);
        }
    });
    socket.on("update_inventory", populateInventory);
    hideBottomDiv();
    showLeftDiv();

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
    hideBottomDiv();
    socket.emit('advance_init', {room: room, charName: charName});
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
        document.getElementById("promptDiv").style.display = "none";
        document.getElementById("promptDiv").innerHTML = "";
        socket.emit('send_initiative', {initiative: tmpInit, charName: charName, room: room});
    } catch (e) {
        socket.emit("error_handle", room, e);
    }
}
function mapClick(e, x, y) {
    try {
        if (isDragging) {
            isDragging = false;
            e.stopPropagation()
            return;
        }
        //console.log("Clicked!" + x + ", " + y);
        relative_y = e.offsetY * 16 / zoomSize;
        relative_x = e.offsetX * 16 / zoomSize;
        //console.log(relative_x + ", " + relative_y);
        if (typeof testEffect !== "undefined"){
            return;
        }
        if (e.currentTarget.attributes.units != ""){
            i = parseInt(e.currentTarget.attributes.units.split(" ")[0]);
            selectUnit(e, i)
            return;
        }
        if (playerData.inInit) {
            socket.emit('locate_unit', {requestingPlayer: charName, moveType: document.getElementById("movementSelector").selectedIndex, selectedUnit: playerData.initiativeList[playerData.initiativeCount].unitNum, xCoord: x, yCoord: y, relative_x: relative_x, relative_y: relative_y, room: room});
        } else {
            if (typeof selectedUnits[0] !== "undefined") {
                socket.emit('locate_unit', {requestingPlayer: charName, selectedUnit: playerData.unitList[selectedUnits[0]].unitNum, xCoord: x, yCoord: y, relative_x: relative_x, relative_y: relative_y, room: room});
                deselectAll();
            } else {
            socket.emit('locate_unit', {requestingPlayer: charName, selectedUnit: playerData.playerList[charName].unitNum, xCoord: x, yCoord: y, relative_x: relative_x, relative_y: relative_y, room: room});
            }
        }
    } catch (error) {
        socket.emit("error_handle", room, error);
    }
}

function selectInitiative(initiativeNum) {
    try {
        for (i=0; i<playerData.unitList.length; i++){
            if (playerData.unitList[i].initNum == initiativeNum) {
                selectUnit([], i);
                return;
            }
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
        //document.getElementById("charWrapper").appendChild( document.getElementById("charDiv"));
        //document.getElementById("joinGameButton").style.display = "none";
        document.getElementById("joinDiv").style.display = "none";
        document.getElementById("screenDiv").style.display = "block";
        charName = document.getElementById("charName").value;
        charShortName = document.getElementById("charShortName").value;
        color = document.getElementById("playerColor").value;
        window.history.replaceState(null, null, window.location.href + `&charName=${charName}`);
        socket.emit('player_join', {room: room, charName: charName, charShortName: charShortName, color: color});
        socket.emit("get_lore", room);
        selectedInventory = charName;
        socket.emit("get_inventories", room, charName);
    } catch (e) {
        socket.emit("error_handle", room, e);
    }
}
function selectUnit(e, unitNum) {
    try {
       if (selectedUnits.length == 0) {
            selectedUnits = [unitNum];
        } else if (selectedUnits.includes(unitNum)) {
            selectedUnits.splice(selectedUnits.indexOf(unitNum), 1)
        } else if (e.shiftKey) {
            tmpUnits = selectedUnits;
            selectedUnits = tmpUnits
            selectedUnits.push(unitNum);
        } else {
            selectedUnits = [unitNum];
        }
        drawSelected(playerData);
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
function updatePlayer () {
    try {
        requestedUpdate = true;
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
        player.movementSpeed = parseInt(document.getElementById("sheetMovementSpeed").value) | 0;
        player.armorSpeed = parseInt(document.getElementById("sheetArmorSpeed").value) | 0;
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

        player.STRTemp = document.getElementById("sheetSTRScoreTemp").value
        player.DEXTemp = document.getElementById("sheetDEXScoreTemp").value
        player.CONTemp = document.getElementById("sheetCONScoreTemp").value
        player.INTTemp = document.getElementById("sheetINTScoreTemp").value
        player.WISTemp = document.getElementById("sheetWISScoreTemp").value
        player.CHATemp = document.getElementById("sheetCHAScoreTemp").value

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
        for (var i = 0; i < document.getElementsByClassName("sheetWeaponName").length; i++) {
            if (document.getElementsByClassName("sheetWeaponName")[i].value == "") {
                continue;
            }

            tmpWeapon = []
            tmpWeapon.push(document.getElementsByClassName("sheetWeaponName")[i].value);
            tmpWeapon.push(document.getElementsByClassName("sheetWeaponAttack")[i].value);
            tmpWeapon.push(document.getElementsByClassName("sheetWeaponDamage")[i].value);
            tmpWeapon.push(document.getElementsByClassName("sheetWeaponCrit")[i].value);
            tmpWeapon.push(document.getElementsByClassName("sheetWeaponType")[i].value);
            tmpWeapon.push(document.getElementsByClassName("sheetWeaponRange")[i].value);
            tmpWeapon.push(document.getElementsByClassName("sheetWeaponAmmo")[i].value);
            player.weapons.push(tmpWeapon);
        }

        player.skills = getSkills();
        player.spellcasting = getSpellcasting();

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
        if (document.getElementById("sheetSTRScoreTemp").value != "") {
            tempScore = parseInt(document.getElementById("sheetSTRScoreTemp").value);
            STRMod = STRMod - Math.floor((score - tempScore)/2);
            document.getElementById("sheetSTRModTemp").value = STRMod
        } else {
            document.getElementById("sheetSTRModTemp").value = "";
        }
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
        if (document.getElementById("sheetDEXScoreTemp").value != "") {
            tempScore = parseInt(document.getElementById("sheetDEXScoreTemp").value);
            DEXMod = DEXMod - Math.floor((score - tempScore)/2);
            document.getElementById("sheetDEXModTemp").value = DEXMod
        } else {
            document.getElementById("sheetDEXModTemp").value = "";
        }
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
        if (document.getElementById("sheetCONScoreTemp").value != "") {
            tempScore = parseInt(document.getElementById("sheetCONScoreTemp").value);
            CONMod = CONMod - Math.floor((score - tempScore)/2);
            document.getElementById("sheetCONModTemp").value = CONMod
        } else {
            document.getElementById("sheetCONModTemp").value = "";
        }
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
        if (document.getElementById("sheetINTScoreTemp").value != "") {
            tempScore = parseInt(document.getElementById("sheetINTScoreTemp").value);
            INTMod = INTMod - Math.floor((score - tempScore)/2);
            document.getElementById("sheetINTModTemp").value = INTMod
        } else {
            document.getElementById("sheetINTModTemp").value = "";
        }
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
        if (document.getElementById("sheetWISScoreTemp").value != "") {
            tempScore = parseInt(document.getElementById("sheetWISScoreTemp").value);
            WISMod = WISMod - Math.floor((score - tempScore)/2);
            document.getElementById("sheetWISModTemp").value = WISMod
        } else {
            document.getElementById("sheetWISModTemp").value = "";
        }
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
        if (document.getElementById("sheetCHAScoreTemp").value != "") {
            tempScore = parseInt(document.getElementById("sheetCHAScoreTemp").value);
            CHAMod = CHAMod - Math.floor((score - tempScore)/2);
            document.getElementById("sheetCHAModTemp").value = CHAMod
        } else {
            document.getElementById("sheetCHAModTemp").value = "";
        }
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
        if (skillsData.Acrobatics) {
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
        }
        return;
    } catch (e) {
        socket.emit("error_handle", room, e);
    }

}
function populateSheet (data) {
    try {

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
        document.getElementById("sheetSTRScoreTemp").value = data.STRTemp;
        if (!isNaN(parseInt(data.STR))) {
            setSTRScore(data.STR);
        }
        document.getElementById("sheetDEXScore").value = data.DEX;
        document.getElementById("sheetDEXScoreTemp").value = data.DEXTemp;
        if (!isNaN(parseInt(data.DEX))) {
        setDEXScore(data.DEX);
        }
        document.getElementById("sheetCONScore").value = data.CON;
        document.getElementById("sheetCONScoreTemp").value = data.CONTemp;
        if (!isNaN(parseInt(data.CON))) {
        setCONScore(data.CON);
        }
        document.getElementById("sheetINTScore").value = data.INT;
        document.getElementById("sheetINTScoreTemp").value = data.INTTemp;
        if (!isNaN(parseInt(data.INT))) {
        setINTScore(data.INT);
        }
        document.getElementById("sheetWISScore").value = data.WIS;
        document.getElementById("sheetWISScoreTemp").value = data.WISTemp;
        if (!isNaN(parseInt(data.WIS))) {
        setWISScore(data.WIS);
        }
        document.getElementById("sheetCHAScore").value = data.CHA;
        document.getElementById("sheetCHAScoreTemp").value = data.CHATemp;
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
        addWeaponForm(true);
        for (var i = 0; i < data.weapons.length; i++) {
            document.getElementsByClassName("sheetWeaponName")[i].value = data.weapons[i][0];
            document.getElementsByClassName("sheetWeaponAttack")[i].value = data.weapons[i][1];
            document.getElementsByClassName("sheetWeaponDamage")[i].value = data.weapons[i][2];
            document.getElementsByClassName("sheetWeaponCrit")[i].value = data.weapons[i][3];
            document.getElementsByClassName("sheetWeaponType")[i].value = data.weapons[i][4];
            document.getElementsByClassName("sheetWeaponRange")[i].value = data.weapons[i][5];
            document.getElementsByClassName("sheetWeaponAmmo")[i].value = data.weapons[i][6];
            addWeaponForm(false);
        }
        spellcasting = data.spellcasting;
        if (data.spellcasting.length > 0) {
            document.getElementById("selectCaster").innerHTML = `Hey, you're an ${data.spellcasting[0].class}`;
            if (data.spellcasting[0].hasSpellbook) {
                document.getElementById("spellbookButton").style.display = "inline-block";
                populateSpellbook(0)
            }
            if (data.spellcasting[0].hasPoints) {
                document.getElementById("spellPoints").style = "block";
                document.getElementById("currentPoints").innerHTML = data.spellcasting[0].currentPoints;
                document.getElementById("dailyPoints").value = data.spellcasting[0].dailyPoints;
            }
            if (data.spellcasting[0].hasSpellSlots) {
                document.getElementById("spellSlots").style = "block";
                document.getElementById("spellSlotsPerDayLVL1").value = data.spellcasting[0].spellSlotsDaily1;
                document.getElementById("spellSlotsPerDayLVL2").value = data.spellcasting[0].spellSlotsDaily2;
                document.getElementById("spellSlotsPerDayLVL3").value = data.spellcasting[0].spellSlotsDaily3;
                document.getElementById("spellSlotsPerDayLVL4").value = data.spellcasting[0].spellSlotsDaily4;
                document.getElementById("spellSlotsPerDayLVL5").value = data.spellcasting[0].spellSlotsDaily5;
                document.getElementById("spellSlotsPerDayLVL6").value = data.spellcasting[0].spellSlotsDaily6;
                document.getElementById("spellSlotsPerDayLVL7").value = data.spellcasting[0].spellSlotsDaily7;
                document.getElementById("spellSlotsPerDayLVL8").value = data.spellcasting[0].spellSlotsDaily8;
                document.getElementById("spellSlotsPerDayLVL9").value = data.spellcasting[0].spellSlotsDaily9;
                displaySpellSlots();
            }
            if (data.spellcasting[0].preparesSpells) {
                document.getElementById("spellPreparedSpellsButton").style = "block";
                document.getElementById("spellsPrepared").style = "block";
                populatePreparedSpells()
            }
        }
        populateSkills(data.skills);
        populateQuickDiv(data);
    } catch (e) {
        socket.emit("error_handle", room, e);
    }
}

function populateQuickDiv(data) {
    removeContents(document.getElementById("bottomInfoDiv"))
    div = document.createElement("div");
    div.innerText = "HP: " + data.HP + "/" + data.maxHP;
    document.getElementById("bottomInfoDiv").appendChild(div);
    if (playerData.inInit && playerData.playerList[charName].flatFooted){
        div = document.createElement("div");
        div.innerText = "AC: " + document.getElementById("sheetFFAC").value;
        document.getElementById("bottomInfoDiv").appendChild(div);

        div = document.createElement("div");
        div.innerText = "Touch AC: " + (parseInt(document.getElementById("sheetTouchAC").value) - parseInt(document.getElementById("sheetDEXMod").value));
        document.getElementById("bottomInfoDiv").appendChild(div);
    } else {
        div = document.createElement("div");
        div.innerText = "AC: " + document.getElementById("sheetACTotal").value;
        document.getElementById("bottomInfoDiv").appendChild(div);

        div = document.createElement("div");
        div.innerText = "Touch AC: " + document.getElementById("sheetTouchAC").value;
        document.getElementById("bottomInfoDiv").appendChild(div);
    }
    div = document.createElement("div");
    div.innerText = "Fortitude Save: " + document.getElementById("sheetFortTotal").value;
    document.getElementById("bottomInfoDiv").appendChild(div);

    div = document.createElement("div");
    div.innerText = "Reflex Save: " + document.getElementById("sheetReflexTotal").value;
    document.getElementById("bottomInfoDiv").appendChild(div);

    div = document.createElement("div");
    div.innerText = "Will Save: " + document.getElementById("sheetWillTotal").value;
    document.getElementById("bottomInfoDiv").appendChild(div);
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
function addWeaponForm(reset) {
    box = document.getElementById("weaponsBox");
    if (reset) {
        box.innerHTML = "";
    }
    newDiv = document.createElement("div");
    newDiv.style.borderStyle = "solid";
    newDiv.style.borderWidth = "2px";
    newDiv.style.marginRight = "0px";
    newDiv.style.float = "left";
    newDiv.style.marginTop = "2px";
    newDiv.innerHTML = `

                <div style="overflow:auto;">
                  <input style="float:left;width:130px;margin:1px;height:22px;margin-right:5px;" class="sheetWeaponName">
                  <input style="float:left;width:60px;margin:1px;height:22px;margin-right:5px;" class="sheetWeaponAttack">
                  <input style="float:left;width:60px;margin:1px;height:22px;" class="sheetWeaponDamage">
                </div><div style="overflow:auto;">
                  <div style="float:left; font-size:0.6em; width:134px;margin-right:5px;margin-left:1px;">Weapon</div>
                  <div style="float:left; font-size:0.6em; width:64px;margin-right:5px;margin-left:1px;">Attack</div>
                  <div style="float:left; font-size:0.6em; width:64px;margin-left:1px;">Damage</div>
                </div><div style="overflow:auto;">
                  <input style="float:left;width:60px;margin:1px;height:22px;margin-right:5px;" class="sheetWeaponCrit">
                  <input style="float:left;width:60px;margin:1px;height:22px;margin-right:5px;" class="sheetWeaponType">
                  <input style="float:left;width:60px;margin:1px;height:22px;margin-right:5px;" class="sheetWeaponRange">
                  <input style="float:left;width:60px;margin:1px;height:22px;" class="sheetWeaponAmmo">
                </div><div style="overflow:auto;">
                  <div style="float:left; font-size:0.6em; width:64px;margin-right:5px;margin-left:1px;">Critical</div>
                  <div style="float:left; font-size:0.6em; width:64px;margin-right:5px;margin-left:1px;">Type</div>
                  <div style="float:left; font-size:0.6em; width:64px;margin-right:5px;margin-left:1px;">Range</div>
                  <div style="float:left; font-size:0.6em; width:64px;">Ammo</div>
                </div>
    `;
    box.append(newDiv);

}
function addSpellcasting() { //function to add an unmanaged spellcasting class
    //we grab the class and level, and send it back to the server
    socket.emit('add_player_spellcasting', {charName: charName, room: room, class: document.getElementById("casterClass").value, level: document.getElementById("casterLevel").value});
    requestedUpdate = true;
}
function modifySpellPoints(change) {
    //document.getElementById("currentPoints").innerHTML = parseInt(document.getElementById("currentPoints").innerHTML) + change;
    spellcasting[0].currentPoints += change;
    updatePlayer();
}
function doRest() {
    currentHP = parseInt(document.getElementById("sheetHP").value) | 0;
    maxHP = parseInt(document.getElementById("sheetMaxHP").value) | 0;
    level = parseInt(document.getElementById("sheetLevel").value) | 0;
    CON = parseInt(document.getElementById("sheetCONMod").value) | 0;
    currentHP = currentHP + CON + level;
    if (currentHP > maxHP) {
        currentHP = maxHP;
    }
    document.getElementById("sheetHP").value = currentHP;
    if (spellcasting[0].hasPoints) {
        //document.getElementById("currentPoints").innerHTML = document.getElementById("dailyPoints").value;
        spellcasting[0].currentPoints = spellcasting[0].dailyPoints;
    }
    if (spellcasting[0].hasSpellSlots) {
        for (l = 1; l<=9; l++){
            spellcasting[0]['spellSlots' + l] = parseInt(spellcasting[0]['spellSlotsDaily' + l]);
        }
        displaySpellSlots();

    }
    if (spellcasting[0].preparesSpells) {
        spellcasting[0].preparedSpells = spellcasting[0].preparedSpellsDaily;
        populatePreparedSpells()
    }
    updatePlayer();
}
function getSpellcasting() {
    if (spellcasting.length > 0) {
        if (spellcasting[0].hasPoints) {
            //spellcasting[0].currentPoints = parseInt(document.getElementById("currentPoints").innerHTML) | 0;
            spellcasting[0].dailyPoints = parseInt(document.getElementById("dailyPoints").value) | 0;
        }
        if (spellcasting[0].hasSpellSlots) {
            spellcasting[0].spellSlotsDaily1 = parseInt(document.getElementById("spellSlotsPerDayLVL1").value) | 0;
            spellcasting[0].spellSlotsDaily2 = parseInt(document.getElementById("spellSlotsPerDayLVL2").value) | 0;
            spellcasting[0].spellSlotsDaily3 = parseInt(document.getElementById("spellSlotsPerDayLVL3").value) | 0;
            spellcasting[0].spellSlotsDaily4 = parseInt(document.getElementById("spellSlotsPerDayLVL4").value) | 0;
            spellcasting[0].spellSlotsDaily5 = parseInt(document.getElementById("spellSlotsPerDayLVL5").value) | 0;
            spellcasting[0].spellSlotsDaily6 = parseInt(document.getElementById("spellSlotsPerDayLVL6").value) | 0;
            spellcasting[0].spellSlotsDaily7 = parseInt(document.getElementById("spellSlotsPerDayLVL7").value) | 0;
            spellcasting[0].spellSlotsDaily8 = parseInt(document.getElementById("spellSlotsPerDayLVL8").value) | 0;
            spellcasting[0].spellSlotsDaily9 = parseInt(document.getElementById("spellSlotsPerDayLVL9").value) | 0;
        }
        if (spellcasting[0].preparesSpells) {
            spellcasting[0].preparedSpellsDaily[0].number = document.getElementById("spellsPreparedPerDayLVL0").value | 0;
            spellcasting[0].preparedSpellsDaily[1].number = document.getElementById("spellsPreparedPerDayLVL1").value | 0;
            spellcasting[0].preparedSpellsDaily[2].number = document.getElementById("spellsPreparedPerDayLVL2").value | 0;
            spellcasting[0].preparedSpellsDaily[3].number = document.getElementById("spellsPreparedPerDayLVL3").value | 0;
            spellcasting[0].preparedSpellsDaily[4].number = document.getElementById("spellsPreparedPerDayLVL4").value | 0;
            spellcasting[0].preparedSpellsDaily[5].number = document.getElementById("spellsPreparedPerDayLVL5").value | 0;
            spellcasting[0].preparedSpellsDaily[6].number = document.getElementById("spellsPreparedPerDayLVL6").value | 0;
            spellcasting[0].preparedSpellsDaily[7].number = document.getElementById("spellsPreparedPerDayLVL7").value | 0;
            spellcasting[0].preparedSpellsDaily[8].number = document.getElementById("spellsPreparedPerDayLVL8").value | 0;
            spellcasting[0].preparedSpellsDaily[9].number = document.getElementById("spellsPreparedPerDayLVL9").value | 0;
        }
    }
    return spellcasting;
}
function castSpellSlot(spllvl) {
    spellcasting[0]["spellSlots" + spllvl] -= 1;
    ourdiv = document.getElementById("spellSlotsLVL" + spllvl);
    ourdiv.removeChild(ourdiv.lastChild);
    updatePlayer();
}
function displaySpellSlots() {
    for (l = 1; l<=9; l++){
            elements = document.getElementById("spellSlotsLVL" + l).getElementsByClassName("spellButton")
            while (elements.length > 0) {
                elements[0].parentNode.removeChild(elements[0]);
            }
            //spellcasting[0]['spellSlots' + l] = parseInt(spellcasting[0]['spellSlotsDaily' + l]);

            for (var i = 0; i < spellcasting[0]['spellSlots' + l]; i++) {
                document.getElementById("spellSlotsLVL" + l).append(document.createElement("button"));
                document.getElementById("spellSlotsLVL" + l).lastChild.innerText = "Cast";
                document.getElementById("spellSlotsLVL" + l).lastChild.className = "spellButton";
                document.getElementById("spellSlotsLVL" + l).lastChild.onclick = (function(l) { return function() { castSpellSlot(l) } })(l);
                }
        }
}
function hackSizes() {
    headerheights = document.getElementById("sheetHeader").offsetHeight + document.getElementById("tabsDiv").offsetHeight + 20;
    document.getElementById("sheetContent").style.height = `calc(100% - ${headerheights}px)`;
}
function addSpell(selectionSource, destination) {
    spellSelectionDestination = destination;
    var modalBackground = document.createElement("div");
    modalBackground.id = "modalBackground";
    modalBackground.className = "modal";
    modalBackground.onclick = function () {document.getElementById('modalBackground').remove();};

    var div = document.createElement("div");
    div.style.width = "80%";
    div.style.height = "90%";
    div.style.position = "absolute";
    div.style.right = "10%";
    div.style.top = "5%";
    div.style.background = "white";
    div.style.border = "black";
    div.style.borderStyle = "solid";
    div.style.borderRadius = "25px";
    div.style.textAlign = "center";
    div.onclick = function () {event.stopPropagation()}
    if (selectionSource == "class") {
        div.innerHTML = `
        Spell Level: <select id="spellLevelSelect" onchange="socket.emit('database_spells', '${spellcasting[0].class}', this.selectedIndex, populateSpellList);">
        <option>0</option>
        <option>1</option>
        <option>2</option>
        <option>3</option>
        <option>4</option>
        <option>5</option>
        <option>6</option>
        <option>7</option>
        <option>8</option>
        <option>9</option>
        </select>
        <div id="selectSpellsDiv" style="height: 50%;overflow: auto;width: 90%;margin: auto;"></div>
        <div id="highlightedSpell" style="overflow: auto;width: 90%;margin: auto;height:40%"></div>
        `;
        document.body.appendChild(modalBackground);
        document.getElementById("modalBackground").appendChild(div);
        document.getElementById("spellLevelSelect").selectedIndex = destination[1]
        socket.emit("database_spells", spellcasting[0].class, destination[1], populateSpellList);
    } else if (selectionSource == "spellbook") {
        div.innerHTML = `
        Spell Level: <select id="spellLevelSelect" onchange="populateSpellList(spellcasting[0].spellbook[this.selectedIndex]);">
        <option>0</option>
        <option>1</option>
        <option>2</option>
        <option>3</option>
        <option>4</option>
        <option>5</option>
        <option>6</option>
        <option>7</option>
        <option>8</option>
        <option>9</option>
        </select>
        <div id="selectSpellsDiv" style="height: 50%;overflow: auto;width: 90%;margin: auto;"></div>
        <div id="highlightedSpell" style="overflow: auto;width: 90%;margin: auto;height:40%"></div>
        `;
            document.body.appendChild(modalBackground);
        document.getElementById("modalBackground").appendChild(div);
        document.getElementById("spellLevelSelect").selectedIndex = destination[1]
        populateSpellList(spellcasting[0].spellbook[destination[1]]);

    }


}
function populateSpellList(results) {
    savedSpellList = results;
    spellLevel = results[0].level;
    if (spellSelectionDestination[0] == "spellbook" && typeof spellcasting[0].spellbook[spellLevel] == "undefined") {
        spellcasting[0].spellbook[spellLevel] = [];
    }
    var spellTable = document.createElement("table");
    spellTable.style.minWidth = "80%";
    spellTable.style.margin = "auto";
    for (i = 0; i < results.length; i++) {
        if (spellSelectionDestination[0] != "spellbook" || spellcasting[0].spellbook[spellLevel].filter( function(spell) {return (spell.name==results[i].name);} ).length == 0) {
            var tableRow = document.createElement("tr");
            tableRow.onclick = (function(i) { return function() { highlightSpell(i) } })(i);
            var tableData = document.createElement("td");
            tableData.innerText = results[i].name;
            tableRow.appendChild(tableData);
            var tableData = document.createElement("td");
            tableData.innerText = results[i].short_description
            var tableData = document.createElement("td");
            var actionButton = document.createElement("button");
            if (spellSelectionDestination[0] == "spellbook") {
                actionButton.innerText = "Add";
                actionButton.onclick = (function(i) { return function() { addSingleSpellToSpellbook(i) } })(i);

            } else if (spellSelectionDestination[0] == "dailyPrepared" ){
                actionButton.innerText = "Prepare";
                actionButton.spell = results[i];
                actionButton.onclick = function() {prepareSpell(this.spell);};
            } else if (spellSelectionDestination[0] == "prepared" ){
                actionButton.innerText = "Prepare";
                actionButton.spell = results[i];
                actionButton.onclick = function() {prepareSpell(this.spell);};
            }
            tableData.appendChild(actionButton);
            tableRow.appendChild(tableData);
            spellTable.appendChild(tableRow);
        }
    }
    document.getElementById("selectSpellsDiv").innerHTML = "";
    document.getElementById("selectSpellsDiv").appendChild(spellTable);
}
function highlightSpell(spellNumber) {
    spellText = savedSpellList[spellNumber].name;
    spellText += savedSpellList[spellNumber].description_formated;
    removeContents(document.getElementById("highlightedSpell"));
    document.getElementById("highlightedSpell").appendChild(formatSpellObj(savedSpellList[spellNumber]));

}
function addSingleSpellToSpellbook(spellNumber) {
    event.stopPropagation();
    spellLevel = savedSpellList[spellNumber].level
    if (typeof spellcasting[0].spellbook[spellLevel] == "undefined") {
        spellcasting[0].spellbook[spellLevel] = [];
    }
    if (spellcasting[0].spellbook[spellLevel].filter( function(spell) {return (spell.name==savedSpellList[spellNumber].name);} ).length == 0) {
        spellcasting[0].spellbook[spellLevel].push(savedSpellList[spellNumber]);
        document.getElementById("highlightedSpell").innerHTML = "";
        populateSpellList(savedSpellList);
        populateSpellbook(0);
    }
}

function populateSpellbook(spellLevel) {
    document.getElementById("spellbookBody").innerHTML = "";
    if (spellLevel == "prepared") {
        for (spellLevel=0; spellLevel<=9; spellLevel++){
            spellcasting[0].preparedSpells[spellLevel].spells = spellcasting[0].preparedSpells[spellLevel].spells.sort(function(a,b){return a.name.localeCompare(b.name)})
            header = document.createElement("div");
            header.innerText = "LVL:" + spellLevel;
            if (spellcasting[0].preparedSpells[spellLevel].spells.length > 0) {
                document.getElementById("spellbookBody").appendChild(header);
            }
            for (i=0; i<spellcasting[0].preparedSpells[spellLevel].spells.length; i++){
                document.getElementById("spellbookBody").appendChild(formatSpellObj(spellcasting[0].preparedSpells[spellLevel].spells[i], false))
            }
        }
    } else {
        if (typeof spellcasting[0].spellbook[spellLevel] == "undefined" || spellcasting[0].spellbook[spellLevel].length == 0){
            document.getElementById("spellbookBody").innerHTML = "No Spells of this Level Yet"
            return;
        }
        for (i=0; i<spellcasting[0].spellbook[spellLevel].length; i++){
            spellcasting[0].spellbook[spellLevel] = spellcasting[0].spellbook[spellLevel].sort(function(a,b){return a.name.localeCompare(b.name)})
            document.getElementById("spellbookBody").appendChild(formatSpellObj(spellcasting[0].spellbook[spellLevel][i], false))
        }
    }
}

function prepareSpell(spell) {
    //player picks slot
    event.stopPropagation();
    document.getElementById('modalBackground').remove();
    console.log(spell);
    if (spellSelectionDestination[0] == "dailyPrepared") {
        spellcasting[0].preparedSpellsDaily[spellSelectionDestination[1]].spells[spellSelectionDestination[2]] = spell;
    } else if (spellSelectionDestination[0] == "prepared") {
        spellcasting[0].preparedSpells[spellSelectionDestination[1]].spells[spellSelectionDestination[2]] = spell;
    }
    updatePlayer();
}

function removeSpell(info) {
    if (info[0] == "dailyPrepared") {
        spellcasting[0].preparedSpellsDaily[info[1]].spells.splice(info[2],1)
        updatePlayer();
    }
}

function populatePreparedSpells() {
    try {
        if (typeof spellcasting[0].castingStat == "undefined") {
            spellcasting[0].castingStat = "INT";
        }
        var castingStat = parseInt(playerData.playerList[charName][spellcasting[0].castingStat]) | 0;
        var castingMod = Math.floor((castingStat - 10) / 2)

        for (i=0; i<9; i++) {
        spellList = "<table style='width:100%;'>";
            if ( typeof spellcasting[0].preparedSpells[i].spells == "undefined") {
                continue;
            }
            if (spellcasting[0].preparedSpellsDaily[i].number > 0) {
                spellList += "<th>LVL" + i + "spells: </th>"
            }
            for (l=0; l<spellcasting[0].preparedSpellsDaily[i].number; l++) {
                spellList += "<tr>";
                if (typeof spellcasting[0].preparedSpells[i].spells[l] == "undefined") {
                    spellList += "<td> </td>";
                    spellList += "<td> </td>";
                    if (spellcasting[0].hasSpellbook){
                    spellList += `<td><button onclick="addSpell('spellbook', ['prepared', ${i}, ${l}])">Prepare</button></td>`;
                    } else {
                    spellList += `<td><button onclick="addSpell('class', ['prepared', ${i}, ${l}])">Prepare</button></td>`;
                    }
                } else if (spellcasting[0].preparedSpells[i].spells[l] == null) {
                    continue;
                } else {
                    spellList += "<td>" + spellcasting[0].preparedSpells[i].spells[l].name + "</td>";
                    spellList += "<td>" + spellcasting[0].preparedSpells[i].spells[l].short_description + "</td>";
                    spellList += "<td>" + spellcasting[0].preparedSpells[i].spells[l].range + "</td>";
                    spellList += "<td>" + spellcasting[0].preparedSpells[i].spells[l].saving_throw + "</td>";
                    spellList += "<td>" + (spellcasting[0].preparedSpells[i].spells[l].level + 10 + castingMod)  + "</td>";
                    spellList += `<td><button onclick='castPreparedSpell(${i}, ${l}, false)' >Cast</button>`;
                    if (spellcasting[0].class == "Arcanist" && spellcasting[0].currentPoints > 0) {
                        spellList += `<button onclick='castPreparedSpell(${i}, ${l}, true)' >Cast Empowered</button>`
                    }
                    spellList += "</td>";
                }
                spellList += "</tr>";
            }
            spellList += "</table>";
            lastTable = document.getElementById("spellsPreparedLVL" + i).lastElementChild;
            if (lastTable != null && lastTable.nodeName == "TABLE") {
                document.getElementById("spellsPreparedLVL" + i).removeChild(lastTable);
            }
            document.getElementById("spellsPreparedLVL" + i).innerHTML += spellList;

        }
        document.getElementById("spellsPrepared").style = "block";

        for (i=0; i<9; i++) {
            spellList = "<table style='width:100%;'>";
            for (l=0; l<spellcasting[0].preparedSpellsDaily[i].number; l++) {
                spellList += "<tr>";
                if (typeof spellcasting[0].preparedSpellsDaily[i].spells[l] != "undefined" && spellcasting[0].preparedSpellsDaily[i].spells[l] != null) {
                    spellList += "<td>" + spellcasting[0].preparedSpellsDaily[i].spells[l].name + "</td>";
                    spellList += "<td>" + spellcasting[0].preparedSpellsDaily[i].spells[l].short_description + "</td>";
                    spellList += `<td><button onclick="removeSpell(['dailyPrepared', ${i}, ${l}])">Remove</button></td>`;
                } else {
                    spellList += "<td>" + "None" + "</td>";
                    spellList += "<td>" + "Available Slot" + "</td>";
                    if (spellcasting[0].hasSpellbook) {
                        source = "spellbook";
                    } else {
                        source = "class";
                    }
                    spellList += `<td><button onclick="addSpell('${source}', ['dailyPrepared', ${i}, ${l}])">Prepare</button></td>`;
                }
                spellList += "</tr>";
            }
            spellList += "</table>";
            lastTable = document.getElementById("spellsPreparedDailyLVL" + i).lastElementChild;
            if (lastTable.nodeName == "TABLE") {
                document.getElementById("spellsPreparedDailyLVL" + i).removeChild(lastTable);
            }
            document.getElementById("spellsPreparedDailyLVL" + i).innerHTML += spellList;

        }

        document.getElementById("spellsPreparedPerDayLVL0").value = spellcasting[0].preparedSpellsDaily[0].number;
        document.getElementById("spellsPreparedPerDayLVL1").value = spellcasting[0].preparedSpellsDaily[1].number;
        document.getElementById("spellsPreparedPerDayLVL2").value = spellcasting[0].preparedSpellsDaily[2].number;
        document.getElementById("spellsPreparedPerDayLVL3").value = spellcasting[0].preparedSpellsDaily[3].number;
        document.getElementById("spellsPreparedPerDayLVL4").value = spellcasting[0].preparedSpellsDaily[4].number;
        document.getElementById("spellsPreparedPerDayLVL5").value = spellcasting[0].preparedSpellsDaily[5].number;
        document.getElementById("spellsPreparedPerDayLVL6").value = spellcasting[0].preparedSpellsDaily[6].number;
        document.getElementById("spellsPreparedPerDayLVL7").value = spellcasting[0].preparedSpellsDaily[7].number;
        document.getElementById("spellsPreparedPerDayLVL8").value = spellcasting[0].preparedSpellsDaily[8].number;
        document.getElementById("spellsPreparedPerDayLVL9").value = spellcasting[0].preparedSpellsDaily[9].number;

    } catch (e) {
        socket.emit("error_handle", room, e);
    }
}

function hideBottomDiv() {
    document.getElementById("mapContainer").style.height = "calc(100% - 40px)";
    document.getElementById("activeTabDiv").style.height = "100%";
    document.getElementById("bottomPopupButton").style.top = "calc(100% - 80px)";
    document.getElementById("bottomPopupButton").onclick = function() {showBottomDiv();};
    document.getElementById("bottomPopupButton").children[0].src = "static/images/up.svg";
    document.getElementById("bottomDiv").style.display="none";
}

function showBottomDiv() {
    document.getElementById("mapContainer").style.height = "100%";
    document.getElementById("activeTabDiv").style.height = "calc(80% - 40px)";
    document.getElementById("bottomPopupButton").style.top = "calc(100% - 40px)";
    document.getElementById("bottomPopupButton").onclick = function() {hideBottomDiv();};
    document.getElementById("bottomPopupButton").children[0].src = "static/images/down.svg";
    document.getElementById("bottomDiv").style.display="block";
    showBottomAttackDiv();
}

function hideLeftDiv() {
    document.getElementById("activeTabDiv").style.width = "100%";
    document.getElementById("activeTabDiv").style.left = "0px";
    document.getElementById("leftPopButton").onclick = function() {showLeftDiv();};
    document.getElementById("leftPopButton").children[0].src = "static/images/right.svg";
    document.getElementById("leftDivContainer").style.display="none";
}

function showLeftDiv() {
    document.getElementById("activeTabDiv").style.width = "80%";
    document.getElementById("activeTabDiv").style.left = "20%";
    document.getElementById("leftPopButton").onclick = function() {hideLeftDiv();};
    document.getElementById("leftPopButton").children[0].src = "static/images/left.svg";
    document.getElementById("leftDivContainer").style.display="block";
}

function hideAllBottomDivs() {
    document.getElementById("bottomAttackDiv").style.display = "none";
    document.getElementById("bottomItemDiv").style.display = "none";
    document.getElementById("bottomSpellDiv").style.display = "none";
    document.getElementById("bottomEffectDiv").style.display = "none";
    document.getElementById("promptDiv").style.display = "none";
}

function showBottomAttackDiv() {
    hideAllBottomDivs();
    removeContents(document.getElementById("bottomAttackDiv"));
    document.getElementById("bottomAttackDiv").style.display = "block";
    var data = playerData.playerList[charName];
    for (var i = 0; i < data.weapons.length; i++) {
        box = document.getElementById("bottomAttackDiv");
        newDiv = document.createElement("div");
        newDiv.style.borderStyle = "solid";
        newDiv.style.borderWidth = "2px";
        newDiv.style.marginRight = "0px";
        newDiv.style.float = "left";
        newDiv.style.marginTop = "2px";
        newDiv.innerHTML = `
            <div style="overflow:auto;">
              <input style="float:left;width:130px;margin:1px;height:22px;margin-right:5px;" class="bottomWeaponName">
              <input style="float:left;width:60px;margin:1px;height:22px;margin-right:5px;" class="bottomWeaponAttack">
              <input style="float:left;width:60px;margin:1px;height:22px;" class="bottomWeaponDamage">
            </div><div style="overflow:auto;">
              <div style="float:left; font-size:0.6em; width:134px;margin-right:5px;margin-left:1px;">Weapon</div>
              <div style="float:left; font-size:0.6em; width:64px;margin-right:5px;margin-left:1px;">Attack</div>
              <div style="float:left; font-size:0.6em; width:64px;margin-left:1px;">Damage</div>
            </div><div style="overflow:auto;">
              <input style="float:left;width:60px;margin:1px;height:22px;margin-right:5px;" class="bottomWeaponCrit">
              <input style="float:left;width:60px;margin:1px;height:22px;margin-right:5px;" class="bottomWeaponType">
              <input style="float:left;width:60px;margin:1px;height:22px;margin-right:5px;" class="bottomWeaponRange">
              <input style="float:left;width:60px;margin:1px;height:22px;" class="bottomWeaponAmmo">
            </div><div style="overflow:auto;">
              <div style="float:left; font-size:0.6em; width:64px;margin-right:5px;margin-left:1px;">Critical</div>
              <div style="float:left; font-size:0.6em; width:64px;margin-right:5px;margin-left:1px;">Type</div>
              <div style="float:left; font-size:0.6em; width:64px;margin-right:5px;margin-left:1px;">Range</div>
              <div style="float:left; font-size:0.6em; width:64px;">Ammo</div>
            </div>`;
        box.append(newDiv);

        document.getElementsByClassName("bottomWeaponName")[i].value = data.weapons[i][0];
        document.getElementsByClassName("bottomWeaponAttack")[i].value = data.weapons[i][1];
        document.getElementsByClassName("bottomWeaponDamage")[i].value = data.weapons[i][2];
        document.getElementsByClassName("bottomWeaponCrit")[i].value = data.weapons[i][3];
        document.getElementsByClassName("bottomWeaponType")[i].value = data.weapons[i][4];
        document.getElementsByClassName("bottomWeaponRange")[i].value = data.weapons[i][5];
        document.getElementsByClassName("bottomWeaponAmmo")[i].value = data.weapons[i][6];
    }

}
function showBottomItemDiv() {
    hideAllBottomDivs();
    document.getElementById("bottomItemDiv").style.display = "block";
}
function showBottomSpellDiv() {
    hideAllBottomDivs();
    document.getElementById("bottomSpellDiv").style.display = "block";

}