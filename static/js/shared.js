const chunk_size = 64 * 1024;
var loreImages = new Array();
var scaling = false;
var prevDiff = 0;
var touchX = 0;
var touchY = 0;
var zoom = 1;
var isDragging = false;
var images = new Object();
var testEffect;
var effects;
var effectCanvas;
var effectCTX;
var defaultBackground = true;
var mapObject;
var inInit;
var currentRound = -1;
var currentInit = -1;
var unitsByUUID;
var crNumbers = ["1/8", "1/6", "1/4", "1/3", "1/2", "1", "2", "3", "4", "5", "6", "7", "8", "9",
                    "10", "11", "12", "13", "14", "15", "16", "17", "18", "19",
                    "20", "21", "22", "23", "24", "25", "26", "27", "28", "29", "30", "35", "37", "39"];
const colors = ["blueviolet","darkorange","dodgerblue","forestgreen","hotpink","lightcoral","mediumspringgreen",
            "olivedrab","salmon","sienna","skyblue","steelblue","tomato"]
if (!('toJSON' in Error.prototype)) {
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
        if (scaling && e.touches.length > 1) {
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
function drawMap(mapData) {
    try {
        mapArray = mapData.mapArray
        if (typeof mapArray[0] === "undefined" ) {
            removeContents(document.getElementById("mapGraphic"));
            document.getElementById("mapForm").style.display = "block";
            document.getElementById("mapGraphic").style.display = "none";
            return;
        }
        removeContents(document.getElementById("mapGraphic"));
        for (y = 0; y < mapArray.length; y++) {
            for (x = 0; x < mapArray[y].length; x++) {
                newMapTile = drawSingleTile(mapData, x, y)
                document.getElementById("mapGraphic").appendChild(newMapTile);
            }
        }
        document.getElementById("mapForm").style.display = "none";
        document.getElementById("mapGraphic").style.display = "block";
        backgroundDiv = document.createElement("div");
        backgroundDiv.id = "mapBackgroundDiv";
        backgroundDiv.style.height = mapArray.length * 70 +"px";
        backgroundDiv.style.width = mapArray[0].length * 70 + "px";
        backgroundDiv.style.position = "absolute";
        backgroundDiv.style.left = "0";
        backgroundDiv.style.top = "0";
        backgroundDiv.style.zIndex = "-1";

        backgroundDiv.style.backgroundImage = "url(" + mapData.mapBackground + ")";
        backgroundDiv.style.backgroundSize = "cover";
        document.getElementById("mapGraphic").appendChild(backgroundDiv);

        effectCanvas = document.createElement("canvas");
        effectCanvas.style.position = "absolute";
        effectCanvas.style.top = 0;
        effectCanvas.style.pointerEvents = "none";
        document.getElementById("mapGraphic").appendChild(effectCanvas);
        effectCanvas.width = mapArray[0].length*70;
        effectCanvas.height = mapArray.length*70;
        effectCTX = effectCanvas.getContext("2d");
    } catch (e) {
        socket.emit("error_handle", room, e);
    }
}
function updateMap(newMapData, mapData) {
    try {
        newMapArray = newMapData.mapArray;
        mapArray = mapData.mapArray;
        for (i = 0; i < newMapArray.length; i++) {
            x = newMapArray[i].x;
            y = newMapArray[i].y;
            mapArray[y][x] = newMapArray[i];
            document.getElementById(`tile${x},${y}`).remove();
            newMapTile = drawSingleTile(mapData, x, y)
            document.getElementById("mapGraphic").appendChild(newMapTile);
        }
        if (newMapData.mapBackground != mapData.mapBackground) {
            document.getElementById("mapBackgroundDiv").style.backgroundImage = "url(" + newMapData.mapBackground + ")";
        }
    } catch (e) {
        socket.emit("error_handle", room, e);
    }
}

function drawSingleTile(mapData, x, y) {
    mapArray = mapData.mapArray
    newMapTile = document.createElement("div");
    newMapTile.id = `tile${x},${y}`;
    newMapTile.onclick = ((x, y) => { return function() { mapClick(event, x, y)
        }
    })(x, y);
    newMapTile.attributes.x = x;
    newMapTile.attributes.y = y;
    newMapTile.attributes.units = "";
    newMapTile.style.width = zoomSize - 2 + "px";
    newMapTile.style.height = zoomSize - 2 + "px";
    newMapTile.style.position = "absolute";
    newMapTile.style.top = y * zoomSize + "px";
    newMapTile.style.left = x * zoomSize + "px";
    if (isGM && mapArray[y][x].secret) {
        newMapTile.style.borderColor = "red";
    }
    newMapTile.className = "mapTile selectableTile";

    if (mapData.mapBackground == "static/images/mapbackground.jpg") {
        newMapTile.classList.add("slightlyTransparent");
    } else if (mapArray[y][x].tile != "unseenTile") {
        newMapTile.classList.add("fullyTransparent");
    }
    if (mapArray[y][x].tile == "unseenTile" && mapData.showBackground) {
        newMapTile.classList.add("unseenTile");
    } else if (mapArray[y][x].tile == "doorOpen") {
        if ((typeof mapArray[y+1] !== "undefined" && mapArray[y+1][x].walkable) || (typeof mapArray[y-1] !== "undefined" && mapArray[y-1][x].walkable)) {
            newMapTile.classList.add("doorTileAOpen");
        } else {
            newMapTile.classList.add("doorTileBOpen");
        }
    } else if (mapArray[y][x].tile == "doorClosed") {
        if ((typeof mapArray[y+1] !== "undefined" && mapArray[y+1][x].walkable) || (typeof mapArray[y-1] !== "undefined" && mapArray[y-1][x].walkable)) {
            if (isGM && mapArray[y][x].locked) {
                newMapTile.classList.add("doorTileALocked");
            } else {
                newMapTile.classList.add("doorTileA");
            }
        } else {
            if (isGM && mapArray[y][x].locked) {
                newMapTile.classList.add("doorTileBLocked");
            } else {
                newMapTile.classList.add("doorTileB");
            }
        }
    } else if (mapArray[y][x].tile == "stairsUp") {
        try {
        if (mapArray[y+1][x].tile =="stairsUp") {
            newMapTile.classList.add("stairTileTop");
        } else if (mapArray[y-1][x].tile =="stairsUp") {
            newMapTile.classList.add("stairTileTop");
        } else if (mapArray[y][x+1].tile =="stairsUp") {
            newMapTile.classList.add("stairTileLeft");
        } else if (mapArray[y][x-1].tile =="stairsUp") {
            newMapTile.classList.add("stairTileLeft");
        } else if (mapArray[y+1][x].walkable || mapArray[y-1][x].walkable) {
            newMapTile.classList.add("stairTileTop");
        } else {
            newMapTile.classList.add("stairTileLeft");
        }
        } catch (error) {
            newMapTile.classList.add("stairTileLeft");
        }
    } else if (mapArray[y][x].tile.includes("stairsDown")) {
        try {
        if (mapArray[y][x+1].tile =="stairsDown" && mapArray[y][x-1].tile.includes("floorTile")) {
            newMapTile.classList.add("stairDownTileRight");
        } else if (mapArray[y][x-1].tile =="stairsDown" && mapArray[y][x+1].tile =="wallTile") {
            newMapTile.classList.add("stairDownDownTileRight");
        } else if (mapArray[y][x-1].tile =="stairsDown" && mapArray[y][x+1].tile.includes("floorTile")) {
            newMapTile.classList.add("stairDownTileLeft");
        } else if (mapArray[y][x+1].tile =="stairsDown" && mapArray[y][x-1].tile =="wallTile") {
            newMapTile.classList.add("stairDownDownTileLeft");
        } else if (mapArray[y+1][x].tile =="stairsDown" && mapArray[y-1][x].tile.includes("floorTile")) {
            newMapTile.classList.add("stairDownTileBottom");
        } else if (mapArray[y-1][x].tile =="stairsDown" && mapArray[y+1][x].tile =="wallTile") {
            newMapTile.classList.add("stairDownDownTileBottom");
        } else if (mapArray[y-1][x].tile =="stairsDown" && mapArray[y+1][x].tile.includes("floorTile")) {
            newMapTile.classList.add("stairDownTileTop");
        } else if (mapArray[y+1][x].tile =="stairsDown" && mapArray[y-1][x].tile =="wallTile") {
            newMapTile.classList.add("stairDownDownTileTop");
        } else {
            newMapTile.classList.add("stairDownDownTileTop");
        }
        } catch (stairerror) {
            newMapTile.classList.add("stairDownDownTileTop");
        }
    } else {
        newMapTile.classList.add(mapArray[y][x].tile);
    }
    if (mapArray[y][x].walls) {
        if (mapArray[y][x].walls.includes("left")) {
            if (newMapTile.style.background != "") {newMapTile.style.background += ",linear-gradient(to left, transparent calc(80%), black calc(80%) calc(100%))";}
            else {newMapTile.style.background = "linear-gradient(to left, transparent calc(80%), black calc(80%) calc(100%))";}
        }
        if (mapArray[y][x].walls.includes("right")) {
            if (newMapTile.style.background != "") {newMapTile.style.background += ",linear-gradient(to right, transparent calc(80%), black calc(80%) calc(100%))"}
            else {newMapTile.style.background += "linear-gradient(to right, transparent calc(80%), black calc(80%) calc(100%))";}
        }
        if (mapArray[y][x].walls.includes("top")) {
            if (newMapTile.style.background != "") {newMapTile.style.background += ",linear-gradient(to top, transparent calc(80%), black calc(80%) calc(100%))"}
            else {newMapTile.style.background += "linear-gradient(to top, transparent calc(80%), black calc(80%) calc(100%))";}
        }
        if (mapArray[y][x].walls.includes("bottom")) {
            if (newMapTile.style.background != "") {newMapTile.style.background += ",linear-gradient(to bottom, transparent calc(80%), black calc(80%) calc(100%))"}
            else {newMapTile.style.background += "linear-gradient(to bottom, transparent calc(80%), black calc(80%) calc(100%))";}
        }
    }
    if (typeof mapArray[y][x].seen !== "undefined") {
        if (isGM && !mapArray[y][x].seen && showSeenOverlay) {
            //newMapTile.style.opacity = ".9";
            newMapTile.style.background = "white";
        }
    }
    return newMapTile

} // There is a lot of needlessly duplicated code in the functions above. Move it here.

function drawUnits(Data) { //Give every addition a classname, that can be iterated through, to remove this stuff.
        //iterate through selectableUnit, remove attributes.units
        nodes = document.getElementsByClassName("selectableUnit");
        while (nodes.length > 0) {
            nodes[0].attributes.units = "";
            nodes[0].classList.remove("selectableUnit");

        }
        nodes = document.getElementsByClassName("unitSpan");
        while (nodes.length > 0) {
            nodes[0].remove();
        }
        nodes = document.getElementsByClassName("moveDot");
        while (nodes.length > 0) {
            nodes[0].remove();
        }
        nodes = document.getElementsByClassName("effectDiv");
        while (nodes.length > 0) {
            nodes[0].remove();
        }
        nodes = document.getElementsByClassName("tokenImg");
        for (var i=nodes.length-1; i >= 0; i-=1) {
            if (!(unitsByUUID[nodes[i].attributes.uuid] && unitsByUUID[nodes[i].attributes.uuid].x != -1)) {
                nodes[i].remove();
            }
        }
        nodes = document.getElementsByClassName("activeUnit");
        while (nodes.length > 0) {
            nodes[0].classList.remove("activeUnit");
        }
        //move the firebrock background into a class

        for (var i = 0; i < Data.unitList.length; i++) {
            if (Data.unitList[i].x !== -1 && document.getElementById(`tile${Data.unitList[i].x},${Data.unitList[i].y}`) !== null) {
                document.getElementById(`tile${Data.unitList[i].x},${Data.unitList[i].y}`).classList.add("selectableUnit");
                document.getElementById(`tile${Data.unitList[i].x},${Data.unitList[i].y}`).attributes.units += i + " ";
                if (typeof Data.unitList[i].size !== "undefined" && Data.unitList[i].size == "large") {
                    document.getElementById(`tile${Data.unitList[i].x+1},${Data.unitList[i].y}`).classList.add("selectableUnit");
                    document.getElementById(`tile${Data.unitList[i].x+1},${Data.unitList[i].y}`).attributes.units += i + " ";
                    document.getElementById(`tile${Data.unitList[i].x},${Data.unitList[i].y-1}`).classList.add("selectableUnit");
                    document.getElementById(`tile${Data.unitList[i].x},${Data.unitList[i].y-1}`).attributes.units += i + " ";
                    document.getElementById(`tile${Data.unitList[i].x+1},${Data.unitList[i].y-1}`).classList.add("selectableUnit");
                    document.getElementById(`tile${Data.unitList[i].x+1},${Data.unitList[i].y-1}`).attributes.units += i + " ";
                }
                if (typeof Data.unitList[i].token === "undefined" || Data.unitList[i].token == "") {
                    tmpSpan = document.createElement("span");
                    tmpSpan.classList.add("unitSpan")
                    tmpSpan.style.color = Data.unitList[i].color;
                    tmpSpan.innerText = Data.unitList[i].charName;
                    document.getElementById(`tile${Data.unitList[i].x},${Data.unitList[i].y}`).appendChild(tmpSpan);
                    if (typeof Data.unitList[i].size !== "undefined" && Data.unitList[i].size == "large") {
                        document.getElementById(`tile${Data.unitList[i].x+1},${Data.unitList[i].y}`).appendChild(tmpSpan.cloneNode(true));
                        document.getElementById(`tile${Data.unitList[i].x},${Data.unitList[i].y-1}`).appendChild(tmpSpan.cloneNode(true));
                        document.getElementById(`tile${Data.unitList[i].x+1},${Data.unitList[i].y-1}`).appendChild(tmpSpan.cloneNode(true));
                    }
                } else {
                    tokenDiv2 = null;
                    nodes = document.getElementsByClassName("tokenImg");
                    for (var x=0; x<nodes.length; x++) {
                        if (nodes[x].attributes.uuid == Data.unitList[i].uuid) {
                            tokenDiv2 = nodes[x];
                            break;
                        }
                    }
                    if (tokenDiv2 == null) {
                        tokenDiv2 = document.createElement("img");
                        tokenDiv2.classList.add("tokenImg");
                        tokenDiv2.src = Data.unitList[i].token;
                        tokenDiv2.style.pointerEvents = "none";
                        tokenDiv2.style.zIndex = "3";
                        tokenDiv2.attributes.uuid = Data.unitList[i].uuid;
                        if (Data.unitList[i].size == "large") {
                            tokenDiv2.style.width = zoomSize*2 - 8 + "px";
                            tokenDiv2.style.height = zoomSize*2  - 8+ "px";
                            tokenDiv2.style.position = "absolute";
                        } else {
                            tokenDiv2.style.width = zoomSize - 8 + "px";
                            tokenDiv2.style.height = zoomSize  - 8 + "px";
                            tokenDiv2.style.position = "absolute";
                        }
                        /*if (Data.inInit && Data.unitList[i].initNum == Data.initiativeCount) {
                            tokenDiv2.style.borderWidth = "4px";
                            tokenDiv2.style.borderStyle = "solid";
                            tokenDiv2.style.borderImage = "radial-gradient(red, transparent)10";
                        }*/
                        document.getElementById("mapGraphic").appendChild(tokenDiv2);
                    } else {
                        if (tokenDiv2.src !== Data.unitList[i].token) {
                            tokenDiv2.src = Data.unitList[i].token;
                        }
                    }
                    //position the tokens

                    position_top = Data.unitList[i].y*zoomSize + 4;
                    position_left = Data.unitList[i].x*zoomSize + 4;
                    if (Data.unitList[i].size == "large") {
                        position_top -= zoomSize;
                    }
                    if (Data.inInit && Data.unitList[i].initNum == Data.initiativeCount) {
                        //position_top -= 4;
                        //position_left -= 4;
                    }
                    tokenDiv2.style.top = position_top + "px";
                    tokenDiv2.style.left = position_left + "px";
                }
            }
        }
        if (typeof effectCTX != "undefined") {
            effectCTX.clearRect(0, 0, effectCanvas.width, effectCanvas.height);
        }
        for (var i = 0; i < Data.effects.length; i++) {
            tmpEffect = generateEffect(Data.effects[i].shape, Data.effects[i].size, Data.effects[i].color);
            if (tmpEffect.shape == "circle") {
                locateEffect(tmpEffect, Data.effects[i].origin.x, Data.effects[i].origin.y);
            } else if (tmpEffect.shape == "line") {
                tmpEffect.end = Data.effects[i].end;
                tmpEffect.origin = Data.effects[i].origin;
                locateEffect(tmpEffect, Data.effects[i].end.x, Data.effects[i].end.y);
            }
        }
        if (Data.inInit) {
            for (i = 0; i<Data.initiativeList[Data.initiativeCount].movePath.length - 1;i++) {
                moveLoc = Data.initiativeList[Data.initiativeCount].movePath[i];
                tmpMovDiv = document.createElement("div");
                tmpMovDiv.classList.add("moveDot");
                tmpMovDiv.style.width = zoomSize/10 + "px";
                tmpMovDiv.style.height = zoomSize/10 + "px";
                tmpMovDiv.style.position = "absolute";
                tmpMovDiv.style.left = moveLoc[1]*zoomSize+zoomSize/2.2 + "px";
                tmpMovDiv.style.top = moveLoc[0]*zoomSize+zoomSize/2.2 + "px";
                tmpMovDiv.style.background = Data.initiativeList[Data.initiativeCount].color;
                document.getElementById("mapGraphic").appendChild(tmpMovDiv);
            }
            if (Data.initiativeList[Data.initiativeCount].x != -1) {
                document.getElementById("tile" + Data.initiativeList[Data.initiativeCount].x + "," + Data.initiativeList[Data.initiativeCount].y).classList.add("activeUnit");
                if (Data.initiativeList[Data.initiativeCount].size == "large") {
                    document.getElementById("tile" + (Data.initiativeList[Data.initiativeCount].x+1) + "," + Data.initiativeList[Data.initiativeCount].y).classList.add("activeUnit");
                    document.getElementById("tile" + Data.initiativeList[Data.initiativeCount].x + "," + (Data.initiativeList[Data.initiativeCount].y-1)).classList.add("activeUnit");
                    document.getElementById("tile" + (Data.initiativeList[Data.initiativeCount].x+1) + "," + (Data.initiativeList[Data.initiativeCount].y-1)).classList.add("activeUnit");
                }
            }
            if (typeof selectedUnits !== "undefined") { //selectedUnit
                for (u=0; u> selectedUnits.length; u++){
                    document.getElementById("tile" + Data.unitList[selectedUnits[u]].x + "," + Data.unitList[selectedUnits[u]].y).classList.add("activeUnit");
                    if (Data.initiativeList[Data.initiativeCount].size == "large") {
                        document.getElementById("tile" + (Data.unitList[selectedUnits[u]].x+1) + "," + Data.unitList[selectedUnits[u]].y).classList.add("activeUnit");
                        document.getElementById("tile" + Data.unitList[selectedUnits[u]].x + "," + (Data.unitList[selectedUnits[u]].y-1)).classList.add("activeUnit");
                        document.getElementById("tile" + (Data.unitList[selectedUnits[u]].x+1) + "," + (Data.unitList[selectedUnits[u]].y-1)).classList.add("activeUnit");
                    }
                }
            }
            document.getElementById("movement").innerText = Math.floor(Data.initiativeList[Data.initiativeCount].distance) * 5
        }
}
function enableTab(tabName) {
    try {
        //hide all of them
        children = document.getElementById("activeTabDiv").children
        for (x = 0; x < children.length; x++) {
            if (children[x].id !== "leftPopButton")
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
            enableLoreTab(i);
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
        //console.log(tabName);
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
            //console.log(document.getElementById("loreURL").value)
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
        //console.log('Upload error for ' + file.name + ': ' + error);
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
    //console.log("imageUpload");
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
            //console.log(document.getElementById("imageURL").value)
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
function generateEffect(effectShape, size, color){
    var effect = {};
    effect.origin = {};
    effect.color = color;
    if (effectShape == "circle") {
        effect.shape = "circle";
        effect.size = size;
        if (effect.size == 0) {
            effect.numSquares = 1;
        } else if (effect.size == 5){
            effect.numSquares = 4;
        } else {
            effect.numSquares = 0;
        }
        effect.divs = [];
        for (i = 0; i< effect.numSquares; i++){
            effect.divs[i] = document.createElement("div");
            effect.divs[i].classList.add("effectDiv");
            effect.divs[i].style.background = color;
            effect.divs[i].style.opacity = 0.5;
            effect.divs[i].style.width = zoomSize + "px";
            effect.divs[i].style.height = zoomSize + "px";
            effect.divs[i].style.position = "absolute";
            effect.divs[i].style.pointerEvents = "none";
        }
    } else if (effectShape == "line") {
        effect.end = {};
        effect.shape = "line";
        effect.size = size;
    }
    return effect;
}
function deleteEffect(effect) {
    if (effect.shape == "circle") {
        for (i = 0; i< effect.numSquares; i++){
            effect.divs[i].remove();
        }
    } else if (effect.shape == "line") {
        effectCTX.clearRect(0, 0, effectCanvas.width, effectCanvas.height)
    }
}
function raytrace(x0, y0, x1, y1, maximum) {  // https://playtechs.blogspot.com/2007/03/raytracing-on-grid.html
    var distance = 0;
    var cells = [];
    var dx = Math.abs(x1 - x0);
    var dy = Math.abs(y1 - y0);
    var x = x0;
    var y = y0;
    var n = 1 + dx + dy;

    if (x1 > x0) {
        x_inc = 1;
    } else {
        x_inc = -1;
    }
    if (y1 > y0) {
        y_inc = 1;
    } else {
        y_inc = -1;
    }
    var error = dx - dy;
    dx *= 2;
    dy *= 2;
    for (i=n; i>0; i--){
        if (Math.max(Math.abs(x0-x), Math.abs(y0-y)) + Math.round(.5 * Math.min(Math.abs(x0-x), Math.abs(y0-y))) > maximum)
            return cells;
        cells.push([x, y]);
        if (error > 0) {
            x += x_inc;
            error -= dy;
        } else {
            y += y_inc;
            error += dx;
        }
    }
    return cells
}
function locateEffect(effect, x, y) {
    if (effect.shape == "circle") {
        if ( effect.origin.x == x && effect.origin.y == y) {
        return;
        }
        effect.origin.x = x;
        effect.origin.y = y;
        if (effect.size == 0) {
            effect.divs[0].style.top = y * 70 + "px";
            effect.divs[0].style.left = x * 70 + "px";
        } else if (effect.size == 5){ // calculate a box, raytrace to each point at the edge of the box... may have to raytrace from 4 squares
            effect.divs[0].style.top = y * 70 + "px";
            effect.divs[0].style.left = x * 70 + "px";
            effect.divs[1].style.top = (y -1) * 70 + "px";
            effect.divs[1].style.left = x * 70 + "px";
            effect.divs[2].style.top = y * 70 + "px";
            effect.divs[2].style.left = (x -1) * 70 + "px";
            effect.divs[3].style.top = (y-1) * 70 + "px";
            effect.divs[3].style.left = (x-1) * 70 + "px";
        } else {
            squares = effect.size / 5;
            var cells = [];
            for (xBox= -1*squares; xBox<squares+1;xBox++) {
                for (yBox= -1*squares; yBox<squares+1; yBox++) {
                    if ((xBox != -1*squares && xBox != squares) && (yBox != -1*squares && yBox != squares)) {
                        continue;
                    }
                    tmpCells = raytrace(effect.origin.x, effect.origin.y, effect.origin.x + xBox, effect.origin.y + yBox, squares-1)
                    for (i=0; i<tmpCells.length; i++) {
                        if (!cells.some(cell => cell[0] == tmpCells[i][0] && cell[1] == tmpCells[i][1])) {
                            cells.push(tmpCells[i]);
                        }
                    }
                    tmpCells = raytrace(effect.origin.x, effect.origin.y-1, effect.origin.x + xBox, effect.origin.y-1 + yBox, squares-1)
                    for (i=0; i<tmpCells.length; i++) {
                        if (!cells.some(cell => cell[0] == tmpCells[i][0] && cell[1] == tmpCells[i][1])) {
                            cells.push(tmpCells[i]);
                        }
                    }
                    tmpCells = raytrace(effect.origin.x-1, effect.origin.y, effect.origin.x-1 + xBox, effect.origin.y + yBox, squares-1)
                    for (i=0; i<tmpCells.length; i++) {
                        if (!cells.some(cell => cell[0] == tmpCells[i][0] && cell[1] == tmpCells[i][1])) {
                            cells.push(tmpCells[i]);
                        }
                    }
                    tmpCells = raytrace(effect.origin.x-1, effect.origin.y-1, effect.origin.x-1 + xBox, effect.origin.y-1 + yBox, squares-1)
                    for (i=0; i<tmpCells.length; i++) {
                        if (!cells.some(cell => cell[0] == tmpCells[i][0] && cell[1] == tmpCells[i][1])) {
                            cells.push(tmpCells[i]);
                        }
                    }
                }
            }
            for (i=0; i<cells.length; i++) {
                //try {
                    if (effect.divs.length < i+1) {
                        effect.numSquares += 1;
                        effect.divs[i] = document.createElement("div");
                        effect.divs[i].classList.add("effectDiv");
                        effect.divs[i].style.background = effect.color;
                        effect.divs[i].style.opacity = 0.5;
                        effect.divs[i].style.width = zoomSize + "px";
                        effect.divs[i].style.height = zoomSize + "px";
                        effect.divs[i].style.position = "absolute";
                        effect.divs[i].style.pointerEvents = "none";
                    }
                    if (cells[i][1] < 0 || cells[i][0] < 0) {
                        effect.divs[i].style.display = "none";
                    } else {
                        effect.divs[i].style.display = "block";
                        effect.divs[i].style.top = cells[i][1] * 70 + "px";
                        effect.divs[i].style.left = cells[i][0] * 70 + "px";
                    }
                //} catch (e) {
                //    console.log("oops");
                //}
            }
        }
    } else if (effect.shape = "line") {
        if (effect.origin && typeof effect.origin.x !== "undefined") {
            playerX = effect.origin.x;
            playerY = effect.origin.y;
        } else {
            if (isGM) {
                if (typeof selectedUnits[0] !== "undefined" && gmData.unitList[selectedUnits[0]].x !== -1) {
                    playerX = gmData.unitList[selectedUnits[0]].x * 70 + 35
                    playerY = gmData.unitList[selectedUnits[0]].y * 70 + 35
                    effect.origin.x = playerX;
                    effect.origin.y = playerY;
                } else if (inInit) {
                    playerX = gmData.initiativeList[gmData.initiativeCount].x * 70 + 35
                    playerY = gmData.initiativeList[gmData.initiativeCount].y * 70 + 35
                    effect.origin.x = playerX;
                    effect.origin.y = playerY;
                } else {
                    return;
                }
            } else {
                playerX = playerData.playerList[charName].x * 70 + 35
                playerY = playerData.playerList[charName].y * 70 + 35
                effect.origin.x = playerX;
                effect.origin.y = playerY;
            }
        }

        angle = Math.atan2(y - playerY, x - playerX) * 180 / Math.PI;
        newPoint = findNewPoint(playerX, playerY, angle, 70 * effect.size / 5);
        if (typeof effectCTX == "undefined") {
            effectCTX = effectCanvas.getContext("2d");
        }
        //effectCTX.clearRect(0, 0, effectCanvas.width, effectCanvas.height);

        effectCTX.beginPath();
        effectCTX.moveTo(playerX, playerY);
        effectCTX.lineTo(newPoint.x, newPoint.y)
        effect.end.x = newPoint.x;
        effect.end.y = newPoint.y;
        effectCTX.lineWidth = 10;
        effectCTX.strokeStyle = effect.color;
        //console.log(newPoint);
        //console.log (playerY);
        effectCTX.stroke();
    }
    if (effect.divs && effect.divs[0].parentNode == null) {
        for (i = 0; i< effect.numSquares; i++){
            document.getElementById("mapGraphic").appendChild(effect.divs[i]);
        }
    }
}
function showEffectControls() {
    table = document.createElement("table");
    table.id = "effectTable";
    tr = document.createElement("tr");
    th = document.createElement("th");
    th.innerText = "Title";
    tr.appendChild(th);
    th = document.createElement("th");
    th.innerText = "shape";
    tr.appendChild(th);
    th = document.createElement("th");
    th.innerText = "size";
    tr.appendChild(th);
    th = document.createElement("th");
    th.innerText = "duration";
    tr.appendChild(th);
    th = document.createElement("th");
    th.innerText = "color";
    tr.appendChild(th);

    table.appendChild(tr);
        if (isGM) {
    document.getElementById("activeTabDiv").style.height = "calc(80% - 40px)";
    document.getElementById("bottomDiv").style.display = "block";
    document.getElementById("showEffectDivButton").onclick = hideEffectControls;
    document.getElementById("bottomDiv").appendChild(table);
    } else {
        hideAllBottomDivs();
        removeContents(document.getElementById("bottomEffectDiv"));
        document.getElementById("bottomEffectDiv").style.display = "block";
        document.getElementById("bottomEffectDiv").appendChild(table);
    }


    for (i=0; i<effects.length; i++) {
        tr = document.createElement("tr");
        td = document.createElement("td");
        td.innerText = effects[i].title;
        tr.appendChild(td);
        td = document.createElement("td");
        td.innerText = effects[i].shape;
        tr.appendChild(td);
        td = document.createElement("td");
        td.innerText = effects[i].size;
        tr.appendChild(td);
        td = document.createElement("td");
        td.innerText = "";
        if (effects[i].duration == "instantaneous") {
            td.innerText = effects[i].duration;
        } else {
            tmpDuration = effects[i].duration;
            if (tmpDuration > 14400){
                tmpNum = Math.floor(tmpDuration / 14400);
                td.innerText += tmpNum + " days ";
                tmpDuration -= tmpNum * 14400;
            } if (tmpDuration > 600){
                tmpNum = Math.floor(tmpDuration / 600);
                td.innerText += tmpNum + " hours ";
                tmpDuration -= tmpNum * 600;
            } if (tmpDuration > 10){
                tmpNum = Math.floor(tmpDuration / 10);
                td.innerText += tmpNum + " minutes ";
                tmpDuration -= tmpNum * 10;
            } if (tmpDuration > 0){
                if (inInit)
                    td.innerText += tmpDuration + " rounds";
                else
                    td.innerText += tmpDuration * 6 + " seconds";
            }
        }
        tr.appendChild(td);
        td = document.createElement("td");
        td.innerText = effects[i].color;
        tr.appendChild(td);
        td = document.createElement("td");
        deleteButton = document.createElement("button");
        deleteButton.innerText = "remove";
        deleteButton.onclick = (function(i) { return function() {effects.splice(i,1); updateEffects(false);  hideEffectControls();}})(i);
        if (isGM || charName == effects[i].owner) {
            td.appendChild(deleteButton);
        }
        tr.appendChild(td);
        table.appendChild(tr);
    }
    tr = document.createElement("tr");
    tr.style.display = "none";
    tr.id = "addEffectRow";
    td = document.createElement("td");
    input = document.createElement("input");
    td.appendChild(input);
    tr.appendChild(td);
    td = document.createElement("td");
    effectShapeSelect = document.createElement("select");
    effectShapeOption = document.createElement("option");
    effectShapeOption.innerText = "Circle";
    effectShapeSelect.appendChild(effectShapeOption);
    effectShapeOption = document.createElement("option");
    effectShapeOption.innerText = "Line";
    effectShapeSelect.appendChild(effectShapeOption);
    effectShapeSelect.onchange = function() {deleteEffect(testEffect); testEffect = generateEffect(effectShapeSelect.value.toLowerCase(), parseInt(effectSizeSelect.value), colorSelect.value);};
    td.appendChild(effectShapeSelect);
    tr.appendChild(td);

    td = document.createElement("td");
    effectSizeSelect = document.createElement("select");
    td.appendChild(effectSizeSelect);
    tr.appendChild(td);

    td = document.createElement("td");
    durationInput = document.createElement("input");
    durationInput.id = "effectDurationInput";
    durationInput.style.display = "none";
    td.appendChild(durationInput);

    durationSpinner = document.createElement("select");
    durationSpinner.onclick = function() {
        if (durationSpinner.value == "instantaneous") {
            durationInput.style.display = "none";
        } else {
            durationInput.style.display = "block";
        }
    }
    durationOption = document.createElement("option");
    durationOption.innerText = "instantaneous";
    durationSpinner.append(durationOption);
    durationOption = document.createElement("option");
    durationOption.innerText = "rounds";
    durationSpinner.append(durationOption);
    durationOption = document.createElement("option");
    durationOption.innerText = "minutes";
    durationSpinner.append(durationOption);
    durationOption = document.createElement("option");
    durationOption.innerText = "hours";
    durationSpinner.append(durationOption);
    durationOption = document.createElement("option");
    durationOption.innerText = "days";
    durationSpinner.append(durationOption);
    td.appendChild(durationSpinner);
    tr.appendChild(td);

    td = document.createElement("td");
    colorSelect = document.createElement("select");
    colorSelect.id = "effectColorPicker";
    colorSelect.onchange = function() {deleteEffect(testEffect); testEffect = generateEffect(effectShapeSelect.value.toLowerCase(), parseInt(effectSizeSelect.value), colorSelect.value);}
    for (i=0;i<colors.length; i++) {
        colorOption = document.createElement("option");
        colorOption.innerText = colors[i];
        colorOption.style.color = colors[i];
        colorSelect.appendChild(colorOption);
    }
    td.appendChild(colorSelect)
    tr.appendChild(td);

    td = document.createElement("td");
    button = document.createElement("button");
    button.innerText = "Cancel";
    button.id = "cancelEffect";

    td.appendChild(button);
    tr.appendChild(td);

    table.appendChild(tr);
    effectSizeSelect.onchange = function() {deleteEffect(testEffect); testEffect = generateEffect(effectShapeSelect.value.toLowerCase(), parseInt(effectSizeSelect.value), colorSelect.value);}
    for (size=0; size<61;size+=5) {
        effectSizeOption = document.createElement("option");
        effectSizeOption.innerText = size;
        effectSizeSelect.appendChild(effectSizeOption);
    }

    tr = document.createElement("tr");
    td = document.createElement("td");
    button = document.createElement("button");
    button.innerText = "Add";
    td.appendChild(button);
    tr.appendChild(td);
    table.appendChild(tr);
    button.onclick = function () {
        document.getElementById("addEffectRow").style.display = "table-row";
        button.style.display = "none";
        if (document.getElementById("passTimeRow"))
            document.getElementById("passTimeRow").style.display = "none";
        testEffect = generateEffect(effectShapeSelect.value.toLowerCase(), 0, "blueviolet");

        document.getElementById("cancelEffect").onclick = function () {
            deleteEffect(testEffect);
            testEffect = undefined;
            button.style.display = "block";
            if (document.getElementById("passTimeRow"))
                document.getElementById("passTimeRow").style.display = "table-row";
            document.getElementById("addEffectRow").style.display = "none";
            document.getElementById("mapContainer").onmousemove = null;
            document.getElementById("mapContainer").onclick = null;
        }
        document.getElementById("mapContainer").onclick = function(e){
            if (isDragging) {
                return;
            }
            e.preventDefault();
            e.stopPropagation();
            testEffect.title = input.value;
            if (durationSpinner.value == "instantaneous" || isNaN(parseInt(durationInput.value))) {
                testEffect.duration = "instantaneous";
            } else if (durationSpinner.value == "rounds") {
                testEffect.duration = parseInt(durationInput.value);
            } else if (durationSpinner.value == "minutes") {
                testEffect.duration = parseInt(durationInput.value) * 10;
            } else if (durationSpinner.value == "hours") {
                testEffect.duration = parseInt(durationInput.value) * 10 * 60;
            } else if (durationSpinner.value == "days") {
                testEffect.duration = parseInt(durationInput.value) * 10 * 60 * 24;
            }
            updateEffects(true);
            deleteEffect(testEffect);
            hideEffectControls();
        }

        document.getElementById("mapContainer").onmousemove = function(e){
            try {
                mouseX = (e.clientX)
                mouseX -= document.getElementById("mapContainer").getBoundingClientRect().x
                mouseX += document.getElementById("mapContainer").scrollLeft;
                mouseX /= zoom;

                mouseY = (e.clientY)
                mouseY -= document.getElementById("mapContainer").getBoundingClientRect().y
                mouseY += document.getElementById("mapContainer").scrollTop;
                mouseY /= zoom;

                if (testEffect.shape == "circle") {
                    if (testEffect.size == 0) {
                        mouseX = Math.floor(mouseX/70)
                        mouseY = Math.floor(mouseY/70)
                    } else {
                        mouseX = Math.round(mouseX/70)
                        mouseY = Math.round(mouseY/70)
                    }
                } else {
                    effectCTX.clearRect(0, 0, effectCanvas.width, effectCanvas.height);
                    for (var i = 0; i < effects.length; i++) {
                        var tmpEffect = generateEffect(effects[i].shape, effects[i].size, effects[i].color);
                        if (tmpEffect.shape == "line") {
                            tmpEffect.end = effects[i].end;
                            tmpEffect.origin = effects[i].origin;
                            locateEffect(tmpEffect, effects[i].end.x, effects[i].end.y);
                        }
                    }
                }

                locateEffect(testEffect, mouseX, mouseY);
            } catch (e) {
                socket.emit("error_handle", room, e);
            }
        }
    }

    tr = document.createElement("tr");
    tr.id = "passTimeRow";
    td = document.createElement("td");
    timeButton = document.createElement("button");
    timeButton.innerText = "Pass Time";
    td.appendChild(timeButton);
    tr.appendChild(td);
    td = document.createElement("td");
    timeInput = document.createElement("input");
    td.appendChild(timeInput);
    tr.appendChild(td);
    td = document.createElement("td");
    timeSpinner = document.createElement("select");

    timeOption = document.createElement("option");
    timeOption.innerText = "rounds";
    timeSpinner.append(timeOption);
    timeOption = document.createElement("option");
    timeOption.innerText = "minutes";
    timeSpinner.append(timeOption);
    timeOption = document.createElement("option");
    timeOption.innerText = "hours";
    timeSpinner.append(timeOption);
    timeOption = document.createElement("option");
    timeOption.innerText = "days";
    timeSpinner.append(timeOption);



    td.appendChild(timeSpinner);
    tr.appendChild(td);
    if (isGM)
        table.appendChild(tr);
    timeButton.onclick = function () {
        timeAdvance = parseInt(timeInput.value);
        if (!isNaN(timeAdvance)) {
            if (timeSpinner.value == "minutes") {
                timeAdvance *= 10;
            } else if (timeSpinner.value == "hours") {
                timeAdvance *= 10 * 60;
            } else if (timeSpinner.value == "days") {
                timeAdvance *= 10 * 60 * 24;
            }
            //updateEffects(true);
            hideEffectControls();
            socket.emit("advance_time", room, timeAdvance, gmKey);
            console.log(timeAdvance);
        }

    }
}
function hideEffectControls() {
    if (typeof testEffect !== "undefined"){

        deleteEffect(testEffect);
        testEffect = undefined;
    }
    document.getElementById("mapContainer").onmousemove = null;
    document.getElementById("mapContainer").onclick = null;
    document.getElementById("effectTable").remove();
    if (isGM) {
    document.getElementById("bottomDiv").style.display = "none";
    document.getElementById("activeTabDiv").style.height = "calc(100% - 40px)";
    }
    document.getElementById("showEffectDivButton").onclick = showEffectControls;
}
function findNewPoint(x, y, angle, distance) { //https://stackoverflow.com/questions/17456783/javascript-figure-out-point-y-by-angle-and-distance
    var result = {};

    result.x = Math.round(Math.cos(angle * Math.PI / 180) * distance + x);
    result.y = Math.round(Math.sin(angle * Math.PI / 180) * distance + y);

    return result;
}
function updateEffects(addnew) {
    if (addnew && typeof testEffect !== "undefined") {
        tempEffect = {};
        tempEffect.shape = testEffect.shape;
        tempEffect.size = testEffect.size;
        tempEffect.origin = testEffect.origin;
        tempEffect.title = testEffect.title;
        tempEffect.color = testEffect.color;
        tempEffect.duration = testEffect.duration;
        if (tempEffect.shape == "line") {
            tempEffect.end = testEffect.end;
        }
        if (isGM) {
            tempEffect.owner = 0;
        } else {
            tempEffect.owner = charName;
        }
        tempEffect.round = currentRound;
        tempEffect.init = currentInit;
        effects.push(tempEffect);
    }
    if (isGM) {
        socket.emit("update_effects", room, effects, gmKey);
    } else {
        socket.emit("update_effects", room, effects, "");
    }
}
function removeContents(el) {
    while(el.firstChild) {
        el.firstChild.remove();
    }
}
function drawSelected(data) {
    nodes = document.getElementsByClassName("selected");
    while (nodes.length > 0) {
        nodes[0].classList.remove("selected");
    }
    for (i=0; i<selectedUnits.length;i++){
        if (typeof document.getElementById("unitsDiv").children[selectedUnits[i]] !== "undefined")
            document.getElementById("unitsDiv").children[selectedUnits[i]].classList.add("selected");
        if (data.unitList[selectedUnits[i]].x !== -1) {
            document.getElementById(`tile${data.unitList[selectedUnits[i]].x},${data.unitList[selectedUnits[i]].y}`).classList.add("selected");
            if (data.unitList[selectedUnits[i]].size == "large") {
                document.getElementById(`tile${data.unitList[selectedUnits[i]].x+1},${data.unitList[selectedUnits[i]].y-1}`).classList.add("selected");
                document.getElementById(`tile${data.unitList[selectedUnits[i]].x},${data.unitList[selectedUnits[i]].y-1}`).classList.add("selected");
                document.getElementById(`tile${data.unitList[selectedUnits[i]].x+1},${data.unitList[selectedUnits[i]].y}`).classList.add("selected");
            }
        }
        if (data.unitList[selectedUnits[i]].initNum != -1) {
            document.getElementById("initiativeDiv").children[data.unitList[selectedUnits[i]].initNum].classList.add("selected");
        }
    }
}
async function chooseCreature() {
    var choice = await new Promise(async function(resolve) {
        var modalBackground = document.createElement("div");
        modalBackground.id = "modalBackground";
        modalBackground.className = "modal";
        modalBackground.onclick = function () {document.getElementById('modalBackground').remove(); resolve(undefined)};

        var modaldiv = document.createElement("div");
        modaldiv.style.width = "80%";
        modaldiv.style.height = "90%";
        modaldiv.style.position = "absolute";
        modaldiv.style.right = "10%";
        modaldiv.style.top = "5%";
        modaldiv.style.background = "white";
        modaldiv.style.border = "black";
        modaldiv.style.borderStyle = "solid";
        modaldiv.style.borderRadius = "25px";
        modaldiv.style.textAlign = "center";
        modaldiv.onclick = function () {event.stopPropagation()}
        document.body.appendChild(modalBackground);
        document.getElementById("modalBackground").appendChild(modaldiv);
        modaldiv.innerText = "CR:";
        crSelect = document.createElement("select");

        for (i=0;i<crNumbers.length;i++) {
            crOption = document.createElement("option");
            crOption.innerText = crNumbers[i];
            crSelect.appendChild(crOption);
        }

        crSelect.onchange = function () {
            populateCreatures(this.value);
        }
        modaldiv.appendChild(crSelect);
        creatureListDiv = document.createElement("div");
        creatureListDiv.style.height = "50%";
        creatureListDiv.style.overflow = "auto";
        creatureListDiv.style.width = "90%";
        creatureListDiv.style.margin = "auto";
        modaldiv.appendChild(creatureListDiv);

        creatureTable = document.createElement("table");
        creatureTable.style.minWidth = "80%";
        creatureTable.style.margin = "auto";
        creatureListDiv.appendChild(creatureTable);

        creatureDetailDiv = document.createElement("div");
        creatureDetailDiv.style.height = "40%";
        creatureDetailDiv.style.overflow = "auto";
        creatureDetailDiv.style.width = "90%";
        creatureDetailDiv.style.margin = "auto";
        modaldiv.appendChild(creatureDetailDiv);
        populateCreatures(crSelect.value);

        async function populateCreatures(CR) {
            removeContents(creatureTable);
            removeContents(creatureDetailDiv);
            msg = await new Promise((resolve, reject) =>  {
                socket.emit("database_creatures", {"cr": CR});
                socket.on("database_creatures_response", function (data) {resolve(data)});
            });

            for (i=0;i<msg.length;i++) {
                var tableRow = document.createElement("tr");

                var tableData = document.createElement("td");
                tableData.innerText = msg[i].Name;
                tableRow.appendChild(tableData);
                var tableData = document.createElement("td");
                tableData.innerText = msg[i].Type;
                tableRow.appendChild(tableData);
                var tableData = document.createElement("td");
                tableData.innerText = msg[i].Size;
                tableRow.appendChild(tableData);
                var tableData = document.createElement("td");
                var button = document.createElement("button");
                button.innerText = "select";
                button.onclick = (function (i) { return function () {
                    document.getElementById('modalBackground').remove();
                    resolve(msg[i]);
                }})(i);
                tableData.appendChild(button);
                tableRow.appendChild(tableData);
                tableRow.onclick = (function (i) { return function () {
                    //show the details of the selected creature here
                    removeContents(creatureDetailDiv);
                    creatureDetailDiv.innerText = msg[i].Name;
                    creatureDetailDiv.innerHTML += "<br>";
                    creatureDetailDiv.innerText += msg[i].Description;
                }})(i);
                creatureTable.appendChild(tableRow);
            }
        }


    })
    return choice;
}
async function selectAddUnit (owner) {
    unitToAdd = await chooseCreature();
    if (typeof unitToAdd == "undefined") {
        return;
    }
    var unit = {};
    unit.charName = unitToAdd.Name;
    unit.color = "black";
    unit.HP = unitToAdd.HP
    unit.maxHP = unit.HP;
    unit.movementSpeed = parseInt(unitToAdd.Speed);
    if (isNaN(unit.movementSpeed)) {
        unit.movementSpeed = 30;
    }
    if (isGM) {
        unit.controlledBy = "gm";
        unit.type = "Mob";
        socket.emit('add_unit', {addToInitiative: false ,unit: unit, room: room, gmKey: gmKey});
    } else {
        unit.type = "Summon";
        unit.controlledBy = charName;
        socket.emit('add_unit', {addToInitiative: inInit ,unit: unit, room: room, charName: charName});
    }
}
function deselectAll() {
    try {
        nodes = document.getElementsByClassName("selected");
        while (nodes.length > 0) {
            nodes[0].classList.remove("selected");
        }
        selectedUnits = [];
        selectedTool = undefined;
    } catch (e) {
        socket.emit("error_handle", room, e);
    }
}