const chunk_size = 64 * 1024;
var loreImages = new Array();
var scaling = false;
var prevDiff = 0;
var touchX = 0;
var touchY = 0;
var zoom = 1;

if (!('toJSON' in Error.prototype))
Object.defineProperty(Error.prototype, 'toJSON', {
    value: function () {
        var alt = {};

        Object.getOwnPropertyNames(this).forEach(function (key) {
            alt[key] = this[key];
        }, this);

        return alt;
    },
    configurable: true,
    writable: true
});
document.getElementById("mapContainer").onwheel = function(e){
    try {
        if (e.ctrlKey){
            e.preventDefault()
            mouseX = (e.clientX - e.currentTarget.getBoundingClientRect().x + e.currentTarget.scrollLeft) / zoomSize;
            mouseY = (e.clientY - e.currentTarget.getBoundingClientRect().y + e.currentTarget.scrollTop) / zoomSize;
            if (e.deltaY < 0) {
                zoomIn(mouseX, mouseY);
            } else if (e.deltaY > 0) {
                zoomOut(mouseX, mouseY);
            }
        }
    } catch (e) {
        socket.emit("error_handle", room, e);
    }
}
document.getElementById("mapContainer").ontouchstart = function(e){
    try {
        if (e.touches.length > 1) {
            e.preventDefault();
            e.stopPropagation();
            scaling = true;
            diff = Math.abs(Math.hypot(e.touches[0].clientX, e.touches[0].clientY) - Math.hypot(e.touches[1].clientX, e.touches[1].clientY));
            touchX = (e.touches[0].clientX + e.touches[1].clientX) /2;
            touchX -= document.getElementById("mapContainer").getBoundingClientRect().x
            touchX += document.getElementById("mapContainer").scrollLeft;
            touchX /= zoom;
            touchY = (e.touches[0].clientY + e.touches[1].clientY) /2;
            touchY -= document.getElementById("mapContainer").getBoundingClientRect().y
            touchY += document.getElementById("mapContainer").scrollTop;
            touchY /= zoom;
            prevDiff = diff;
        }
    } catch (e) {
        socket.emit("error_handle", room, e);
    }
}
document.getElementById("mapContainer").ontouchmove = function(e){
    try {
        if (scaling & e.touches.length > 1) {
            e.preventDefault();
            e.stopPropagation();
            diff = Math.abs(Math.hypot(e.touches[0].clientX, e.touches[0].clientY) - Math.hypot(e.touches[1].clientX, e.touches[1].clientY));
            if (Math.abs( diff - prevDiff) > 10) {
                if (diff > prevDiff ) {
                    //zoomIn();
                    zoom *= 1.1; //add max zoom
                } else {
                    //zoomOut()
                    zoom /= 1.1 //add min zoom
                }
                    document.getElementById("mapGraphic").style.transform = `scale(${zoom})`;
                    document.getElementById("mapContainer").scrollLeft = touchX*zoom - document.getElementById("mapContainer").clientWidth/2
                    document.getElementById("mapContainer").scrollTop = touchY*zoom - document.getElementById("mapContainer").clientHeight/2
                prevDiff = diff
            }
            //
        }
    } catch (e) {
        socket.emit("error_handle", room, e);
    }
}
document.getElementById("mapContainer").ontouchend = function(e){
    try {
        if (scaling) {
            scaling = false;
            e.preventDefault();
            e.stopPropagation();
        }
    } catch (e) {
        socket.emit("error_handle", room, e);
    }

}
function updateMap(Data) {
    try {
        if (typeof Data.mapArray[0] === "undefined" ) {
            document.getElementById("mapGraphic").innerHTML = "";
            document.getElementById("mapForm").style.display = "block";
            document.getElementById("mapGraphic").style.display = "none";
            document.getElementById("zoomControls").style.display = "none";
        } else {
            newMapText = "";
            for (x = 0; x < Data.mapArray.length; x++) {
                for (y = 0; y < Data.mapArray[x].length; y++) {
                    newMapText += `<div id="tile${x},${y}" onclick="mapClick(event, ${x}, ${y})" x="${x}" y="${y}" units=""`;
                    newMapText += `style="width:${zoomSize}px;height:${zoomSize}px;position:absolute;top:${x*zoomSize}px;left:${y*zoomSize}px;`;
                    if (typeof Data.mapArray[x][y].seen !== "undefined") {
                        if (!Data.mapArray[x][y].seen && showSeenOverlay) {
                            newMapText += 'opacity:.5;';
                        }
                    }
                    if (Data.mapArray[x][y].secret) {
                        newMapText += 'border-color:red;';
                    }
                    newMapText += '"';
                    newMapText += `class='mapTile selectableTile `;
                    if (Data.mapArray[x][y].tile == "doorOpen") {
                        if ((typeof Data.mapArray[x+1] !== "undefined" && Data.mapArray[x+1][y].walkable) || (typeof Data.mapArray[x-1] !== "undefined" && Data.mapArray[x-1][y].walkable)) {
                            newMapText += "doorTileAOpen";
                        } else {
                            newMapText += "doorTileBOpen";
                        }
                    } else if (Data.mapArray[x][y].tile == "doorClosed") {
                        if (Data.mapArray[x+1][y].walkable || Data.mapArray[x-1][y].walkable) {
                            newMapText += "doorTileA";
                        } else {
                            newMapText += "doorTileB";
                        }
                    } else if (Data.mapArray[x][y].tile == "stairsUp") {
                        if (Data.mapArray[x+1][y].tile =="stairsUp") {
                            newMapText += "stairTileTop";
                        } else if (Data.mapArray[x-1][y].tile =="stairsUp") {
                            newMapText += "stairTileTop";
                        } else if (Data.mapArray[x][y+1].tile =="stairsUp") {
                            newMapText += "stairTileLeft";
                        } else if (Data.mapArray[x][y-1].tile =="stairsUp") {
                            newMapText += "stairTileLeft";
                        } else if (Data.mapArray[x+1][y].walkable || Data.mapArray[x-1][y].walkable) {
                            newMapText += "stairTileTop";
                        } else {
                            newMapText += "stairTileLeft";
                        }
                    } else if (Data.mapArray[x][y].tile.includes("stairsDown")) {
                        if (Data.mapArray[x][y+1].tile =="stairsDown" && Data.mapArray[x][y-1].tile.includes("floorTile")) {
                            newMapText += "stairDownTileRight";
                        } else if (Data.mapArray[x][y-1].tile =="stairsDown" && Data.mapArray[x][y+1].tile =="wallTile") {
                            newMapText += "stairDownDownTileRight";
                        } else if (Data.mapArray[x][y-1].tile =="stairsDown" && Data.mapArray[x][y+1].tile.includes("floorTile")) {
                            newMapText += "stairDownTileLeft";
                        } else if (Data.mapArray[x][y+1].tile =="stairsDown" && Data.mapArray[x][y-1].tile =="wallTile") {
                            newMapText += "stairDownDownTileLeft";
                        } else if (Data.mapArray[x+1][y].tile =="stairsDown" && Data.mapArray[x-1][y].tile.includes("floorTile")) {
                            newMapText += "stairDownTileBottom";
                        } else if (Data.mapArray[x-1][y].tile =="stairsDown" && Data.mapArray[x+1][y].tile =="wallTile") {
                            newMapText += "stairDownDownTileBottom";
                        } else if (Data.mapArray[x-1][y].tile =="stairsDown" && Data.mapArray[x+1][y].tile.includes("floorTile")) {
                            newMapText += "stairDownTileTop";
                        } else if (Data.mapArray[x+1][y].tile =="stairsDown" && Data.mapArray[x-1][y].tile =="wallTile") {
                            newMapText += "stairDownDownTileTop";
                        } else {
                            newMapText += "stairDownDownTileTop";
                        }
                    } else {
                        newMapText += Data.mapArray[x][y].tile;
                    }
                    newMapText += `'>`;
                    newMapText += "</div>";
                }
                    newMapText += "<br>";
            }
            document.getElementById("mapGraphic").innerHTML = newMapText;
            document.getElementById("mapForm").style.display = "none";
            document.getElementById("mapGraphic").style.display = "inline-block";
            document.getElementById("zoomControls").style.display = "block";
            for (var i = 0; i < Data.unitList.length; i++) {
                if (typeof Data.unitList[i].x !== "undefined" && document.getElementById(`tile${Data.unitList[i].x},${Data.unitList[i].y}`) !== null) {
                    if (typeof Data.unitList[i].token === "undefined" || Data.unitList[i].token == "") {
                        if (typeof Data.unitList[i].charShortName === "undefined" || Data.unitList[i].charShortName == "") {
                            Data.unitList[i].charShortName = Data.unitList[i].charName
                        }
                        tmpHTML = `<div style="color:${Data.unitList[i].color}">`;
                        if (Data.unitList[i].charName.length * 10 <= zoomSize) {
                            tmpHTML += Data.unitList[i].charName;
                        } else {
                            tmpHTML += Data.unitList[i].charShortName;
                        }
                        tmpHTML += "</div>";
                        document.getElementById(`tile${Data.unitList[i].x},${Data.unitList[i].y}`).innerHTML += tmpHTML;
                        document.getElementById(`tile${Data.unitList[i].x},${Data.unitList[i].y}`).className += " selectableUnit";
                        document.getElementById(`tile${Data.unitList[i].x},${Data.unitList[i].y}`).attributes.units.value += i + " ";
                        if (typeof Data.unitList[i].size !== "undefined" && Data.unitList[i].size == "large") {
                            document.getElementById(`tile${Data.unitList[i].x-1},${Data.unitList[i].y}`).innerHTML += tmpHTML;
                            document.getElementById(`tile${Data.unitList[i].x-1},${Data.unitList[i].y}`).className += " selectableUnit"
                            document.getElementById(`tile${Data.unitList[i].x-1},${Data.unitList[i].y}`).attributes.units.value += i + " ";
                            document.getElementById(`tile${Data.unitList[i].x},${Data.unitList[i].y+1}`).innerHTML += tmpHTML;
                            document.getElementById(`tile${Data.unitList[i].x},${Data.unitList[i].y+1}`).className += " selectableUnit"
                            document.getElementById(`tile${Data.unitList[i].x},${Data.unitList[i].y+1}`).attributes.units.value += i + " ";
                            document.getElementById(`tile${Data.unitList[i].x-1},${Data.unitList[i].y+1}`).innerHTML += tmpHTML;
                            document.getElementById(`tile${Data.unitList[i].x-1},${Data.unitList[i].y+1}`).className += " selectableUnit"
                            document.getElementById(`tile${Data.unitList[i].x-1},${Data.unitList[i].y+1}`).attributes.units.value += i + " ";
                        }
                    } else {
                        document.getElementById(`tile${Data.unitList[i].x},${Data.unitList[i].y}`).className += " selectableUnit";
                        document.getElementById(`tile${Data.unitList[i].x},${Data.unitList[i].y}`).attributes.units.value += i + " ";
                        tokenDiv = '<img src="' + Data.unitList[i].token + '" ';
                        if (Data.unitList[i].size == "large") {
                            tokenDiv += `style="pointer-events: none; width:${zoomSize*2}px;height:${zoomSize*2}px;position:absolute;top:${Data.unitList[i].x*zoomSize-zoomSize}px;left:${Data.unitList[i].y*zoomSize}px;"`;
                        } else {
                            tokenDiv += `style="pointer-events: none; width:${zoomSize}px;height:${zoomSize}px;position:absolute;top:${Data.unitList[i].x*zoomSize}px;left:${Data.unitList[i].y*zoomSize}px;"`;
                        }
                        tokenDiv += '</img>'; //Add the image of the appropriate size/location
                        document.getElementById("mapGraphic").innerHTML += tokenDiv;
                    }
                }
            }
            if (Data.inInit /*&& Data.initiativeList[Data.initiativeCount].movePath.length > 0*/) {
                tmpHTML = ""
                for (i = 0; i<Data.initiativeList[Data.initiativeCount].movePath.length - 1;i++) {
                    moveLoc = Data.initiativeList[Data.initiativeCount].movePath[i];
                    tmpHTML += `<div style="width:${zoomSize/10}px;height:${zoomSize/10}px;position:absolute;top:${moveLoc[0]*zoomSize+zoomSize/2.2}px;left:${moveLoc[1]*zoomSize+zoomSize/2.2}px;background:${Data.initiativeList[Data.initiativeCount].color};"></div>`;
                }
                if (Data.initiativeList[Data.initiativeCount].x != -1)
                document.getElementById("tile" + Data.initiativeList[Data.initiativeCount].x + "," + Data.initiativeList[Data.initiativeCount].y).style.background = "cornflowerblue";
                if (Data.initiativeList[Data.initiativeCount].size == "large") {
                    document.getElementById("tile" + (Data.initiativeList[Data.initiativeCount].x - 1) + "," + Data.initiativeList[Data.initiativeCount].y).style.background = "cornflowerblue";
                    document.getElementById("tile" + Data.initiativeList[Data.initiativeCount].x + "," + (Data.initiativeList[Data.initiativeCount].y + 1)).style.background = "cornflowerblue";
                    document.getElementById("tile" + (Data.initiativeList[Data.initiativeCount].x - 1) + "," + (Data.initiativeList[Data.initiativeCount].y + 1)).style.background = "cornflowerblue";
                }
                document.getElementById("mapGraphic").innerHTML += tmpHTML
                document.getElementById("movement").innerText = Math.floor(Data.initiativeList[Data.initiativeCount].distance) * 5
            }
        }
    } catch (e) {
        socket.emit("error_handle", room, e);
    }
}
function enableTab(tabName) {
    try {
        //hide all of them
        children = document.getElementById("activeTabDiv").children
        for (x = 0; x < children.length; x++) {
            children[x].style.display = "none";
        }
        document.getElementById(tabName).style.display="block";
        if (tabName == "inventory") {
        document.getElementById('register').scrollTop = document.getElementById('register').scrollHeight
        document.getElementById('items').scrollTop = document.getElementById('items').scrollHeight
        }
        //show the one that was passed
    } catch (e) {
        socket.emit("error_handle", room, e);
    }
}
function populateEditChar (Data, unitNum) {
    try {
        if (Data.unitList.length == 0) {return}
        for (x = 0; x < Data.unitList.length; x++){
            if (Data.unitList[x].unitNum == unitNum){
                playerUnitNum = x;
                break;
            }
        }
        document.getElementById("editCharNum").innerText = playerUnitNum;
        document.getElementById("charactername").innerText = Data.unitList[playerUnitNum].charName;

        if (Data.unitList[playerUnitNum].token == "") {
            document.getElementById("unitTokenView").src = "static/images/profile.svg";
        } else {
            document.getElementById("unitTokenView").src = Data.unitList[playerUnitNum].token;
        }
        if (Data.unitList[playerUnitNum].token != "" && document.getElementById("charTokenView") != null) {
            document.getElementById("charTokenView").src = Data.unitList[playerUnitNum].token;
        }
        if (Data.unitList[playerUnitNum].image != "" && document.getElementById("charImageView") != null) {
            document.getElementById("charImageView").src = Data.unitList[playerUnitNum].image;
        }
        document.getElementById("charShortName").value = Data.unitList[playerUnitNum].charShortName;
        document.getElementById("playerColor").value = Data.unitList[playerUnitNum].color;
        document.getElementById("customColor").value = Data.unitList[playerUnitNum].color;
        if (document.getElementById("playerColor").value == "") {
            document.getElementById("customColorDiv").style.display = "block";
            document.getElementById("playerColor").value = "custom";
        } else {
            document.getElementById("customColorDiv").style.display = "none";
        }
        document.getElementById("passivePerception").value = Data.unitList[playerUnitNum].perception;
        document.getElementById("movementSpeed").value = Data.unitList[playerUnitNum].movementSpeed;
        document.getElementById("dex").value = Data.unitList[playerUnitNum].DEX;
        document.getElementById("size").value = Data.unitList[playerUnitNum].size;
        document.getElementById("darkvision").checked = Data.unitList[playerUnitNum].darkvision;
        document.getElementById("lowLight").checked = Data.unitList[playerUnitNum].lowLight;
        document.getElementById("trapfinding").checked = Data.unitList[playerUnitNum].trapfinding;
        //document.getElementById("hasted").checked = Data.unitList[playerUnitNum].hasted;
        document.getElementById("permanentAbilities").value = Data.unitList[playerUnitNum].permanentAbilities;
        if (isGM) {
            document.getElementById("init").value = Data.unitList[playerUnitNum].initiative;
            document.getElementById("revealsMap").checked = Data.unitList[playerUnitNum].revealsMap;
        } else {
        document.getElementById("sheetCharName").value = Data.unitList[playerUnitNum].charName;
        }
    } catch (e) {
        socket.emit("error_handle", room, e);
    }
}
function updateImages (unitInfo) {
    try {
        if (unitInfo.token != "" && document.getElementById("charTokenView") != null) {
            document.getElementById("charTokenView").src = unitInfo.token;
        }
        if (unitInfo.image != "" && document.getElementById("charImageView") != null) {
            document.getElementById("charImageView").src = unitInfo.image;
        }
    } catch (e) {
        socket.emit("error_handle", room, e);
    }
}
function previewLoreFile () {
    try {
        document.getElementById("loreFilePreview").src = URL.createObjectURL(document.getElementById("loreFileUpload").files[0])
    } catch (e) {
        socket.emit("error_handle", room, e);
    }
}
function uploadLore () { //https://github.com/miguelgrinberg/socketio-examples
    try {
        if (typeof document.getElementById("loreFileUpload").files[0] == "undefined") {
            return;
        }
        //FReader = new FileReader();
        Name = document.getElementById('loreFileUpload').value;
        file = document.getElementById('loreFileUpload').files[0];
        socket.emit('lore_upload', room, file.size, document.getElementById("loreName").value, document.getElementById("loreText").value, charName, function(loreSlot) {//we prime the server
            this.loreSlot = loreSlot; // and then get back the data needed to do the rest of the transfer.
            readFileChunk(file, 0, chunk_size,
                onReadSuccess.bind(this),
                onReadError.bind(this));
        }.bind(file));
    } catch (e) {
        socket.emit("error_handle", room, e);
    }
}
function readFileChunk(file, offset, length, success, error) {
    try {
        end_offset = offset + length;
        if (end_offset > file.size)
            end_offset = file.size;
        var r = new FileReader();
        r.onload = function(file, offset, length, e) {
            if (e.target.error != null)
                error(file, offset, length, e.target.error);
            else
                success(file, offset, length, e.target.result);
        }.bind(r, file, offset, length);
        r.readAsArrayBuffer(file.slice(offset, end_offset));
    } catch (e) {
        socket.emit("error_handle", room, e);
    }
}
function onReadSuccess(file, offset, length, data) {
    try {
        if (this.done)
            return;
        if (!socket.connected) {
            // the WebSocket connection was lost, wait until it comes back
            setTimeout(onReadSuccess.bind(this, file, offset, length, data), 5000);
            return;
        }
        socket.emit('write_chunk', room, this.loreSlot, offset, data, function(offset, ack) {
            if (!ack)
                onReadError(this.file, offset, 0, 'Transfer aborted by server')
        }.bind(this, offset));
        end_offset = offset + length;
        document.getElementById("uploadProgress").style.width = parseInt(300 * end_offset / file.size) + "px";
        if (end_offset < file.size)
            readFileChunk(file, end_offset, chunk_size,
                onReadSuccess.bind(this),
                onReadError.bind(this));
        else {
            this.done = true;
            socket.emit("get_lore", room);
        }
    } catch (e) {
        socket.emit("error_handle", room, e);
    }
}
function updateLore(msg, num) {
    try {
        document.getElementById("lorePage").innerHTML = "";
        document.getElementById("loreTabs").innerHTML = "";
        for (i=0; i< msg.length; i++) {
            if(isGM || msg[i].loreVisible || msg[i].loreOwner == charName) {
                tmpHTML = `<div class="loreTab" id="loreTab${i}" style="display:none;" id=loreTab${i}>`;
                if (typeof msg[i].loreSize == "undefined" || msg[i].loreSize == 0) {
                    tmpHTML += `<img class="loreIMG" id="loreIMG${i}" src="${msg[i].loreURL}"></img>`;
                } else {
                    tmpHTML += `<img class="loreIMG" id="loreIMG${i}"></img>`;
                }
                tmpHTML += `<br><span>${msg[i].loreText}</span><br>`;
                if (isGM || msg[i].loreOwner == charName) {
                    tmpHTML += `Visible: <input onclick="changeLoreVisibility(${i})" type="checkbox" ${(msg[i].loreVisible) ? "checked" : ""}><br>`;
                    tmpHTML += `<button onclick="deleteLore(${i})">Delete</button><br>`;
                }
                tmpHTML += "</div>";
                document.getElementById("lorePage").innerHTML += tmpHTML
                document.getElementById("loreTabs").innerHTML += `<div class="tab" onClick="enableLoreTab('${i}')">${msg[i].loreName}</div>`;
                if (typeof msg[i].loreSize !== "undefined" && msg[i].loreSize !== 0) {
                    if (typeof loreImages[i] == "undefined") {
                        downloadLoreImage(i)
                    } else {
                        document.getElementById(`loreIMG${i}`).src = "data:image;base64, " + loreImages[i];
                    }
                }
            }
        }

        if (isGM || typeof charName !== "undefined") {
            document.getElementById("lorePage").innerHTML += `<div id="loreTab${i}" style="display:none;"><img id="loreFilePreview"></img><br>` +
                `Image Link:<input type="text" id="loreURL" onchange="previewLoreURL(this.value)"><br>` +
                `Or upload a file: <input type="file" id="loreFileUpload" onchange="previewLoreFile()"><br>` +
                `<div style="background:blue; height: 40px; width:0px;" id="uploadProgress"></div>` +
                `Name: <input type="text" id="loreName"><br>` +
                `Text: <textarea id="loreText"></textarea><br>` +
                `<button onclick="sendLoreURL()">Send</button></div>`;
                document.getElementById("loreTabs").innerHTML += `<div class="tab" onClick="enableLoreTab('${i}')">Add</div>`;
        } else {
            //document.getElementById("lorePage").innerHTML += `<div style="display:none;"></div>`;
            //document.getElementById("loreTabs").innerHTML += `<div class="tab" onClick="enableLoreTab('${i}')">Blank</div>`;
        }
        if (num == null) {
            enableLoreTab(0);
        } else {
            enableLoreTab(num);
            enableTab("lore");

        }
    } catch (e) {
        socket.emit("error_handle", room, e);
    }
}
function enableLoreTab(tabName) {
    try {
        console.log(tabName);
        //hide all of them
        children = document.getElementById("lorePage").children
        for (x = 0; x < children.length; x++) {
            children[x].style.display = "none";
        }
        document.getElementById(`loreTab${tabName}`).style.display = "block"
    } catch (e) {
        socket.emit("error_handle", room, e);
    }
}
function changeLoreVisibility(i) {
    try {
        if (isGM) {
            socket.emit("lore_visible", room, gmKey, i);
        } else {
            socket.emit("lore_visible", room, charName, i);
        }
    } catch (e) {
        socket.emit("error_handle", room, e);
    }
}
function deleteLore(i) {
    try {
        if (isGM) {
            socket.emit("delete_lore", room, gmKey, i);
        } else {
            socket.emit("delete_lore", room, charName, i);
        }
    } catch (e) {
        socket.emit("error_handle", room, e);
    }
}
function sendLoreURL () {
    try {
        if (document.getElementById("loreFileUpload").value == "") {
            console.log(document.getElementById("loreURL").value)
            socket.emit("lore_url", room, document.getElementById("loreURL").value, document.getElementById("loreName").value, document.getElementById("loreText").value, charName);
        } else {
            uploadLore();
        }
    } catch (e) {
        socket.emit("error_handle", room, e);
    }
}
function previewLoreURL (value) {
    try {
        document.getElementById("loreFilePreview").src = value;
    } catch (e) {
        socket.emit("error_handle", room, e);
    }
}
function onReadError(file, offset, length, error) {
    try {
        console.log('Upload error for ' + file.name + ': ' + error);
        this.done = true;
    } catch (e) {
        socket.emit("error_handle", room, e);
    }
}
function downloadLoreImage(slotNum) {
    try {
        socket.emit("get_lore_file", room, slotNum, function (returnedImage){
            loreImages[slotNum] = returnedImage;
            document.getElementById(`loreIMG${slotNum}`).src = "data:image;base64, " + loreImages[slotNum];
        })
    } catch (e) {
        socket.emit("error_handle", room, e);
    }
}
function changeItemCat(target) {
    try {
        if (target.value == "Custom") {
            document.getElementById("itemSelect").style.display = "none"
            document.getElementById("itemText").style.display = "block"
        } else {
            document.getElementById("itemSelect").style.display = "block"
            document.getElementById("itemText").style.display = "none"
        }
    } catch (e) {
        socket.emit("error_handle", room, e);
    }
}
function handle_error(e) {

    socket.emit("error_handle", room, e);
}
function imageUpload(element, title, character) {
    console.log("imageUpload");
    var modalBackground = document.createElement("div");
    modalBackground.id = "modalBackground";
    modalBackground.className = "modal";
    modalBackground.onclick = function () {document.getElementById('modalBackground').remove()}

    var div = document.createElement("div");
    div.style.minWidth = "50%";
    div.style.minHeight = "50%";
    div.style.position = "absolute";
    div.style.right = "25%";
    div.style.top = "10%";
    div.style.background = "white";
    div.style.border = "black";
    div.style.borderStyle = "solid";
    div.style.borderRadius = "25px";
    div.style.textAlign = "center";
    div.onclick = function () {event.stopPropagation()}
    div.innerHTML = `Image Link:<input type="text" id="imageURL" onchange="previewImageURL(this.value)">
    <button>Preview</button>
    <br>
    Or upload a file: <input type="file" id="imageFileUpload" onchange="previewImageFile(this)"><br>
    <img id="imagePreview" src="" style = "padding:20px;"><br>
    <button onClick = "selectImage('${title}', '${character}')">Select</button>
    `;

    document.body.appendChild(modalBackground);
    document.getElementById("modalBackground").appendChild(div);
}
function previewImageURL(value) {
    try {
        document.getElementById("imageFileUpload").value = "";
        document.getElementById("imagePreview").src = value;
    } catch (e) {
        socket.emit("error_handle", room, e);
    }
}
function previewImageFile (callingElement) {
    try {
        document.getElementById("imageURL").value = "";
        document.getElementById("imagePreview").src = URL.createObjectURL(callingElement.files[0])
    } catch (e) {
        socket.emit("error_handle", room, e);
    }
}
function selectImage (title, character) {
    try {
        if (document.getElementById("imageFileUpload").value == "") {
            console.log(document.getElementById("imageURL").value)
            socket.emit("image_upload", room, document.getElementById("imageURL").value, title, character);
            document.getElementById('modalBackground').remove()
        } else {
            if (typeof document.getElementById("imageFileUpload").files[0] == "undefined") {
                return;
            }
            //FReader = new FileReader();
            Name = document.getElementById('imageFileUpload').value;
            file = document.getElementById('imageFileUpload').files[0];
            var r = new FileReader();
            r.onload = function() {
                socket.emit("image_upload", room, "data:image;base64, " + btoa(r.result), title, character);
                document.getElementById('modalBackground').remove();
            }
            r.readAsBinaryString(file);
        }
    } catch (e) {
        socket.emit("error_handle", room, e);
    }
}
function showSheetPage(pageName) {
    elements = document.getElementsByClassName("sheetPage");
    for (var i = 0; i < elements.length; i++) {
        elements[i].style.display = "none";
    }
    document.getElementById(pageName).style.display = "block";
}
function get_spells (casterClass, level, callback) {
    socket.emit("database_spells", casterClass, level, callback)
}
function formatSpell(spell, showPrepare) { //probably obsolete
    try {
        console.log("Warning, using obsolete formatSpell()")
        spellText = "<div class='spellBlock'>";
        spellText += "<div class='spellName'>";
        spellText += spell.name;
        if (showPrepare) {
            spellText += ` <button onclick="prepareSpellDaily('${spell.name}')">Prepare</button>`;
        }
        spellText += "</div>";
        spellText += "<b>School:</b> " + spell.school;
        if (spell.subschool != "") {
            spellText += " (" + spell.subschool + ")";
        }
        if (spell.descriptor != "") {
            spellText += " [" + spell.descriptor + "]";
        }

        spellText += "<p><b>Casting Time:</b> "+ spell.casting_time;
        spellText += "<br><b>Components:</b> "+ spell.components;

        spellText += "<p><b>Range:</b> "+ spell.range;
        if (spell.area != "") {
            spellText += "<br><b>Area:</b> "+ spell.area;
        }
        if (spell.targets != "") {
            spellText += "<br><b>Targets:</b> "+ spell.targets;
        }
        spellText += "<br><b>Duration:</b> "+ spell.duration;
        spellText += "<br><b>Saving Throw:</b> "+ spell.saving_throw;
        spellText += " <b>Spell Resistance:</b> "+ spell.spell_resistence;
        spellText += spell.description_formated;
        spellText += "</div>";
        return spellText
    } catch (e) {
        socket.emit("error_handle", room, e);
    }
}


function formatSpellObj(spell, showPrepare) {
    try {
        var spellObj = document.createElement("div");
        spellObj.className = "spellBlock";

        var spellName = document.createElement("div");
        spellName.className = "spellName";
        spellName.innerText = spell.name;
        if (showPrepare) {
            var prepareButton = document.createElement("button");
            prepareButton.innerText = "Prepare";
            prepareButton.spell = spell;
            prepareButton.onclick = function () {prepareSpellDaily(this);};
            spellName.appendChild(prepareButton);
        }
        spellObj.appendChild(spellName);
        var spellTextObj = document.createElement("div");
        spellText = "<b>School:</b> " + spell.school;
        if (spell.subschool != "") {
            spellText += " (" + spell.subschool + ")";
        }
        if (spell.descriptor != "") {
            spellText += " [" + spell.descriptor + "]";
        }

        spellText += "<p><b>Casting Time:</b> "+ spell.casting_time;
        spellText += "<br><b>Components:</b> "+ spell.components;

        spellText += "<p><b>Range:</b> "+ spell.range;
        if (spell.area != "") {
            spellText += "<br><b>Area:</b> "+ spell.area;
        }
        if (spell.targets != "") {
            spellText += "<br><b>Targets:</b> "+ spell.targets;
        }
        spellText += "<br><b>Duration:</b> "+ spell.duration;
        spellText += "<br><b>Saving Throw:</b> "+ spell.saving_throw;
        spellText += " <b>Spell Resistance:</b> "+ spell.spell_resistence;
        spellText += spell.description_formated;
        spellTextObj.innerHTML = spellText;
        spellObj.appendChild(spellTextObj);

        return spellObj
    } catch (e) {
        socket.emit("error_handle", room, e);
    }
}


function populatePreparedSpells() {
    try {


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
                    if (spellcasting.hasSpellBook){
                    spellList += `<td><button onclick="addSpell('spellbook', ['prepared', ${i}, ${l}])">Prepare</button></td>`;
                    } else {
                    spellList += `<td><button onclick="addSpell('class', ['prepared', ${i}, ${l}])">Prepare</button></td>`;
                    }
                } else if (spellcasting[0].preparedSpells[i].spells[l] == null) {
                    continue;
                } else {
                    spellList += "<td>" + spellcasting[0].preparedSpells[i].spells[l].name + "</td>";
                    spellList += "<td>" + spellcasting[0].preparedSpells[i].spells[l].short_description + "</td>";
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
                    if (spellcasting[0].hasSpellBook) {
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

function castPreparedSpell (spellLvl, spellNum, empowered) {
    if (empowered) {
        spellcasting[0].currentPoints -= 1;
    }
    if (spellLvl > 0) {
        if (spellcasting[0].Vancian) {
            spellcasting[0].preparedSpells[spellLvl].spells[spellNum] = null;
        } else if (spellcasting[0].hasSpellSlots){
            spellcasting[0]["spellSlots" + spellLvl] -= 1;
            if (spellcasting[0]["spellSlots" + spellLvl] == 0) {
                spellcasting[0].preparedSpells[spellLvl].number = 0;
                for (i=0; i<spellcasting[0].preparedSpellsDaily[spellLvl].number; i++) {
                    spellcasting[0].preparedSpells[spellLvl].spells[i] = null;
                }
            }

        }
    }
   updatePlayer();
}