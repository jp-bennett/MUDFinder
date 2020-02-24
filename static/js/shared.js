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
var defaultBackground = true;
var mapObject;
const colors = ["blueviolet","darkorange","dodgerblue","forestgreen","hotpink","lightcoral","mediumspringgreen",
            "olivedrab","salmon","sienna","skyblue","steelblue","tomato"]

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

function drawMap(mapArray) {
    try {
        if (typeof mapArray[0] === "undefined" ) {
            removeContents(document.getElementById("mapGraphic"));
            document.getElementById("mapForm").style.display = "block";
            document.getElementById("mapGraphic").style.display = "none";
            return;
        }
        removeContents(document.getElementById("mapGraphic")); //TODO: eventually make needed changes only
        for (y = 0; y < mapArray.length; y++) {
            for (x = 0; x < mapArray[y].length; x++) {
                newMapTile = document.createElement("div");
                newMapTile.id = `tile${x},${y}`;
                newMapTile.onclick = ((x, y) => { return function() { mapClick(event, x, y)
                }
                })(x, y);
                newMapTile.attributes.x = x;
                newMapTile.attributes.y = y;
                newMapTile.attributes.units = "";
                newMapTile.style.width = zoomSize + "px";
                newMapTile.style.height = zoomSize + "px";
                newMapTile.style.position = "absolute";
                newMapTile.style.top = y * zoomSize + "px";
                newMapTile.style.left = x * zoomSize + "px";
                if (typeof mapArray[y][x].seen !== "undefined") {
                    if (isGM && !mapArray[y][x].seen && showSeenOverlay) {
                        newMapTile.style.opacity = ".9";
                    }
                }
                if (mapArray[y][x].secret) {
                    newMapTile.style.borderColor = "red";
                }
                newMapTile.className = "mapTile selectableTile";
                if (defaultBackground) {
                    newMapTile.classList.add("slightlyTransparent");
                }
                if (mapArray[y][x].tile == "unseenTile" && defaultBackground) {
                    newMapTile.classList.add("unseenTileTransparent");
                } else if (mapArray[y][x].tile == "doorOpen") {
                    if ((typeof mapArray[y+1] !== "undefined" && mapArray[y+1][x].walkable) || (typeof mapArray[y-1] !== "undefined" && mapArray[y-1][x].walkable)) {
                        newMapTile.classList.add("doorTileAOpen");
                    } else {
                        newMapTile.classList.add("doorTileBOpen");
                    }
                } else if (mapArray[y][x].tile == "doorClosed") {
                    if ((typeof mapArray[y+1] !== "undefined" && mapArray[y+1][x].walkable) || (typeof mapArray[y-1] !== "undefined" && mapArray[y-1][x].walkable)) {
                        newMapTile.classList.add("doorTileA");
                    } else {
                        newMapTile.classList.add("doorTileB");
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
                document.getElementById("mapGraphic").appendChild(newMapTile);
            }
        }
        document.getElementById("mapForm").style.display = "none";
        document.getElementById("mapGraphic").style.display = "block";
        backgroundDiv = document.createElement("div");
        backgroundDiv.style.height = mapArray.length * 70 +"px";
        backgroundDiv.style.width = mapArray[0].length * 70 + "px";
        backgroundDiv.style.position = "absolute";
        backgroundDiv.style.left = "0";
        backgroundDiv.style.top = "0";
        backgroundDiv.style.zIndex = "-1";
        if (defaultBackground) {
            backgroundDiv.style.backgroundImage = "url(static/images/mapbackground.jpg)";
            document.getElementById("mapGraphic").appendChild(backgroundDiv);
        }
    } catch (e) {
        socket.emit("error_handle", room, e);
    }
}

function updateMap(newMapArray, mapArray) {
    try {
        for (i = 0; i < newMapArray.length; i++) {
            x = newMapArray[i].x;
            y = newMapArray[i].y;
            mapArray[y][x] = newMapArray[i]

            document.getElementById(`tile${x},${y}`).remove();
            newMapTile = document.createElement("div");
            newMapTile.id = `tile${x},${y}`;
            newMapTile.onclick = ((x, y) => { return function() { mapClick(event, x, y)
            }
            })(x, y);
            newMapTile.attributes.x = x;
            newMapTile.attributes.y = y;
            newMapTile.attributes.units = "";
            newMapTile.style.width = zoomSize + "px";
            newMapTile.style.height = zoomSize + "px";
            newMapTile.style.position = "absolute";
            newMapTile.style.top = y * zoomSize + "px";
            newMapTile.style.left = x * zoomSize + "px";
            if (typeof mapArray[y][x].seen !== "undefined") {
                if (isGM && !mapArray[y][x].seen && showSeenOverlay) {
                    newMapTile.style.opacity = ".9";
                }
            }
            if (mapArray[y][x].secret) {
                newMapTile.style.borderColor = "red";
            }
            newMapTile.className = "mapTile selectableTile";
            if (defaultBackground) {
                newMapTile.classList.add("slightlyTransparent");
            }
            if (mapArray[y][x].tile == "unseenTile" && defaultBackground) {
                newMapTile.classList.add("unseenTileTransparent");
            } else if (mapArray[y][x].tile == "doorOpen") {
                if ((typeof mapArray[y+1] !== "undefined" && mapArray[y+1][x].walkable) || (typeof mapArray[y-1] !== "undefined" && mapArray[y-1][x].walkable)) {
                    newMapTile.classList.add("doorTileAOpen");
                } else {
                    newMapTile.classList.add("doorTileBOpen");
                }
            } else if (mapArray[y][x].tile == "doorClosed") {
                if ((typeof mapArray[y+1] !== "undefined" && mapArray[y+1][x].walkable) || (typeof mapArray[y-1] !== "undefined" && mapArray[y-1][x].walkable)) {
                    newMapTile.classList.add("doorTileA");
                } else {
                    newMapTile.classList.add("doorTileB");
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
            document.getElementById("mapGraphic").appendChild(newMapTile);
        }
    } catch (e) {
        socket.emit("error_handle", room, e);
    }
}

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
        while (nodes.length > 0) {
            nodes[0].remove();
        }
        nodes = document.getElementsByClassName("activeUnit");
        while (nodes.length > 0) {
            nodes[0].classList.remove("activeUnit");
        }
        //move the firebrock background into a class
        for (var i = 0; i < Data.unitList.length; i++) {
            if (typeof Data.unitList[i].x !== "undefined" && document.getElementById(`tile${Data.unitList[i].x},${Data.unitList[i].y}`) !== null) {
                document.getElementById(`tile${Data.unitList[i].x},${Data.unitList[i].y}`).classList.add("selectableUnit");
                document.getElementById(`tile${Data.unitList[i].x},${Data.unitList[i].y}`).attributes.units += i + " ";
                if (typeof Data.unitList[i].size !== "undefined" && Data.unitList[i].size == "large") {

                document.getElementById(`tile${Data.unitList[i].x},${Data.unitList[i].y}`).classList.add("selectableUnit");
                    document.getElementById(`tile${Data.unitList[i].x-1},${Data.unitList[i].y}`).attributes.units += i + " ";
                document.getElementById(`tile${Data.unitList[i].x},${Data.unitList[i].y}`).classList.add("selectableUnit");
                    document.getElementById(`tile${Data.unitList[i].x},${Data.unitList[i].y+1}`).attributes.units += i + " ";
                document.getElementById(`tile${Data.unitList[i].x},${Data.unitList[i].y}`).classList.add("selectableUnit");
                    document.getElementById(`tile${Data.unitList[i].x-1},${Data.unitList[i].y+1}`).attributes.units += i + " ";
                }
                if (typeof Data.unitList[i].token === "undefined" || Data.unitList[i].token == "") {
                    tmpSpan = document.createElement("span");
                    tmpSpan.classList.add("unitSpan")
                    tmpSpan.style.color = Data.unitList[i].color;
                    tmpSpan.innerText = Data.unitList[i].charName;
                    document.getElementById(`tile${Data.unitList[i].x},${Data.unitList[i].y}`).appendChild(tmpSpan);
                    if (typeof Data.unitList[i].size !== "undefined" && Data.unitList[i].size == "large") {
                        document.getElementById(`tile${Data.unitList[i].x-1},${Data.unitList[i].y}`).appendChild(tmpSpan);
                        document.getElementById(`tile${Data.unitList[i].x},${Data.unitList[i].y+1}`).appendChild(tmpSpan);
                        document.getElementById(`tile${Data.unitList[i].x-1},${Data.unitList[i].y+1}`).appendChild(tmpSpan);
                    }
                } else {
                    tokenDiv2 = document.createElement("img");
                    tokenDiv2.classList.add("tokenImg");
                    tokenDiv2.src = Data.unitList[i].token;
                    tokenDiv2.style.pointerEvents = "none"
                    position_top = Data.unitList[i].y*zoomSize + 4;
                    position_left = Data.unitList[i].x*zoomSize + 4;
                    if (Data.unitList[i].size == "large") {
                        position_top -= zoomSize;
                        tokenDiv2.style.width = zoomSize*2 - 8 + "px";
                        tokenDiv2.style.height = zoomSize*2  - 8+ "px";
                        tokenDiv2.style.position = "absolute";
                    } else {
                        tokenDiv2.style.width = zoomSize - 8 + "px";
                        tokenDiv2.style.height = zoomSize  - 8 + "px";
                        tokenDiv2.style.position = "absolute";
                    }
                    if (Data.inInit && Data.unitList[i].initNum == Data.initiativeCount) {
                        tokenDiv2.style.borderWidth = "5px";
                        tokenDiv2.style.borderStyle = "solid";
                        tokenDiv2.style.borderImage = "radial-gradient(red, transparent)10";
                        position_top -= 5;
                        position_left -= 5;
                    }
                    tokenDiv2.style.top = position_top + "px";
                    tokenDiv2.style.left = position_left + "px";
                    document.getElementById("mapGraphic").appendChild(tokenDiv2);
                }
            }
        }
        for (var i = 0; i < Data.effects.length; i++) {
            tmpEffect = generateEffect(Data.effects[i].shape, Data.effects[i].size, Data.effects[i].color);
            locateEffect(tmpEffect, Data.effects[i].origin.x, Data.effects[i].origin.y);
        }
        if (Data.inInit) {
            for (i = 0; i<Data.initiativeList[Data.initiativeCount].movePath.length - 1;i++) {
                moveLoc = Data.initiativeList[Data.initiativeCount].movePath[i];
                tmpMovDiv = document.createElement("div");
                tmpMovDiv.classList.add("moveDot");
                tmpMovDiv.style.width = zoomSize/10 + "px";
                tmpMovDiv.style.height = zoomSize/10 + "px";
                tmpMovDiv.style.position = "absolute";
                tmpMovDiv.style.left = moveLoc[0]*zoomSize+zoomSize/2.2 + "px";
                tmpMovDiv.style.top = moveLoc[1]*zoomSize+zoomSize/2.2 + "px";
                tmpMovDiv.style.background = Data.initiativeList[Data.initiativeCount].color;
                document.getElementById("mapGraphic").appendChild(tmpMovDiv);
            }
            if (Data.initiativeList[Data.initiativeCount].x != -1) {
                document.getElementById("tile" + Data.initiativeList[Data.initiativeCount].x + "," + Data.initiativeList[Data.initiativeCount].y).classList.add("activeUnit");
                if (Data.initiativeList[Data.initiativeCount].size == "large") {
                    document.getElementById("tile" + (Data.initiativeList[Data.initiativeCount].x - 1) + "," + Data.initiativeList[Data.initiativeCount].y).classList.add("activeUnit");
                    document.getElementById("tile" + Data.initiativeList[Data.initiativeCount].x + "," + (Data.initiativeList[Data.initiativeCount].y + 1)).classList.add("activeUnit");
                    document.getElementById("tile" + (Data.initiativeList[Data.initiativeCount].x - 1) + "," + (Data.initiativeList[Data.initiativeCount].y + 1)).classList.add("activeUnit");
                }
            }
            if (typeof selectedUnits !== "undefined") { //selectedUnit
                for (u=0; u> selectedUnits.length; u++){
                    document.getElementById("tile" + Data.unitList[selectedUnits[u]].x + "," + Data.unitList[selectedUnits[u]].y).classList.add("activeUnit");
                    if (Data.initiativeList[Data.initiativeCount].size == "large") {
                        document.getElementById("tile" + (Data.unitList[selectedUnits[u]].x - 1) + "," + Data.unitList[selectedUnits[u]].y).classList.add("activeUnit");
                        document.getElementById("tile" + Data.unitList[selectedUnits[u]].x + "," + (Data.unitList[selectedUnits[u]].y + 1)).classList.add("activeUnit");
                        document.getElementById("tile" + (Data.unitList[selectedUnits[u]].x - 1) + "," + (Data.unitList[selectedUnits[u]].y + 1)).classList.add("activeUnit");
                    }
                }
            }
            document.getElementById("movement").innerText = Math.floor(Data.initiativeList[Data.initiativeCount].distance) * 5
        }
}

/*function updateMap(Data) {
    try {
        if (typeof Data.mapArray[0] === "undefined" ) {
            removeContents(document.getElementById("mapGraphic"));
            document.getElementById("mapForm").style.display = "block";
            document.getElementById("mapGraphic").style.display = "none";
            return;
        }
        removeContents(document.getElementById("mapGraphic")); //TODO: eventually make needed changes only
        for (x = 0; x < Data.mapArray.length; x++) {
            for (y = 0; y < Data.mapArray[x].length; y++) {
                newMapTile = document.createElement("div");
                newMapTile.id = `tile${x},${y}`;
                newMapTile.onclick = ((x, y) => { return function() { mapClick(event, x, y)
                }
                })(x, y);
                newMapTile.attributes.x = x;
                newMapTile.attributes.y = y;
                newMapTile.attributes.units = "";
                newMapTile.style.width = zoomSize + "px";
                newMapTile.style.height = zoomSize + "px";
                newMapTile.style.position = "absolute";
                newMapTile.style.top = x * zoomSize + "px";
                newMapTile.style.left = y * zoomSize + "px";
                if (typeof Data.mapArray[x][y].seen !== "undefined") {
                    if (!Data.mapArray[x][y].seen && showSeenOverlay) {
                        newMapTile.style.opacity = ".9";
                    }
                }
                if (Data.mapArray[x][y].secret) {
                    newMapTile.style.borderColor = "red";
                }
                newMapTile.className = "mapTile selectableTile";
                if (defaultBackground) {
                    newMapTile.classList.add("slightlyTransparent");
                }
                if (Data.mapArray[x][y].tile == "unseenTile" && defaultBackground) {
                    newMapTile.classList.add("unseenTileTransparent");
                } else if (Data.mapArray[x][y].tile == "doorOpen") {
                    if ((typeof Data.mapArray[x+1] !== "undefined" && Data.mapArray[x+1][y].walkable) || (typeof Data.mapArray[x-1] !== "undefined" && Data.mapArray[x-1][y].walkable)) {
                        newMapTile.classList.add("doorTileAOpen");
                    } else {
                        newMapTile.classList.add("doorTileBOpen");
                    }
                } else if (Data.mapArray[x][y].tile == "doorClosed") {
                    if ((typeof Data.mapArray[x+1] !== "undefined" && Data.mapArray[x+1][y].walkable) || (typeof Data.mapArray[x-1] !== "undefined" && Data.mapArray[x-1][y].walkable)) {
                        newMapTile.classList.add("doorTileA");
                    } else {
                        newMapTile.classList.add("doorTileB");
                    }
                } else if (Data.mapArray[x][y].tile == "stairsUp") {
                    try {
                    if (Data.mapArray[x+1][y].tile =="stairsUp") {
                        newMapTile.classList.add("stairTileTop");
                    } else if (Data.mapArray[x-1][y].tile =="stairsUp") {
                        newMapTile.classList.add("stairTileTop");
                    } else if (Data.mapArray[x][y+1].tile =="stairsUp") {
                        newMapTile.classList.add("stairTileLeft");
                    } else if (Data.mapArray[x][y-1].tile =="stairsUp") {
                        newMapTile.classList.add("stairTileLeft");
                    } else if (Data.mapArray[x+1][y].walkable || Data.mapArray[x-1][y].walkable) {
                        newMapTile.classList.add("stairTileTop");
                    } else {
                        newMapTile.classList.add("stairTileLeft");
                    }
                    } catch (error) {
                        newMapTile.classList.add("stairTileLeft");
                    }
                } else if (Data.mapArray[x][y].tile.includes("stairsDown")) {
                    try {
                    if (Data.mapArray[x][y+1].tile =="stairsDown" && Data.mapArray[x][y-1].tile.includes("floorTile")) {
                        newMapTile.classList.add("stairDownTileRight");
                    } else if (Data.mapArray[x][y-1].tile =="stairsDown" && Data.mapArray[x][y+1].tile =="wallTile") {
                        newMapTile.classList.add("stairDownDownTileRight");
                    } else if (Data.mapArray[x][y-1].tile =="stairsDown" && Data.mapArray[x][y+1].tile.includes("floorTile")) {
                        newMapTile.classList.add("stairDownTileLeft");
                    } else if (Data.mapArray[x][y+1].tile =="stairsDown" && Data.mapArray[x][y-1].tile =="wallTile") {
                        newMapTile.classList.add("stairDownDownTileLeft");
                    } else if (Data.mapArray[x+1][y].tile =="stairsDown" && Data.mapArray[x-1][y].tile.includes("floorTile")) {
                        newMapTile.classList.add("stairDownTileBottom");
                    } else if (Data.mapArray[x-1][y].tile =="stairsDown" && Data.mapArray[x+1][y].tile =="wallTile") {
                        newMapTile.classList.add("stairDownDownTileBottom");
                    } else if (Data.mapArray[x-1][y].tile =="stairsDown" && Data.mapArray[x+1][y].tile.includes("floorTile")) {
                        newMapTile.classList.add("stairDownTileTop");
                    } else if (Data.mapArray[x+1][y].tile =="stairsDown" && Data.mapArray[x-1][y].tile =="wallTile") {
                        newMapTile.classList.add("stairDownDownTileTop");
                    } else {
                        newMapTile.classList.add("stairDownDownTileTop");
                    }
                    } catch (stairerror) {
                        newMapTile.classList.add("stairDownDownTileTop");
                    }
                } else {
                    newMapTile.classList.add(Data.mapArray[x][y].tile);
                }
                document.getElementById("mapGraphic").appendChild(newMapTile);
            }
        }

        //document.getElementById("mapGraphic").innerHTML = newMapText;
        document.getElementById("mapForm").style.display = "none";
        document.getElementById("mapGraphic").style.display = "block";

        for (var i = 0; i < Data.unitList.length; i++) {
            if (typeof Data.unitList[i].x !== "undefined" && document.getElementById(`tile${Data.unitList[i].x},${Data.unitList[i].y}`) !== null) {
                document.getElementById(`tile${Data.unitList[i].x},${Data.unitList[i].y}`).classList.add("selectableUnit");
                document.getElementById(`tile${Data.unitList[i].x},${Data.unitList[i].y}`).attributes.units += i + " ";
                if (typeof Data.unitList[i].size !== "undefined" && Data.unitList[i].size == "large") {

                document.getElementById(`tile${Data.unitList[i].x},${Data.unitList[i].y}`).classList.add("selectableUnit");
                    document.getElementById(`tile${Data.unitList[i].x-1},${Data.unitList[i].y}`).attributes.units += i + " ";
                document.getElementById(`tile${Data.unitList[i].x},${Data.unitList[i].y}`).classList.add("selectableUnit");
                    document.getElementById(`tile${Data.unitList[i].x},${Data.unitList[i].y+1}`).attributes.units += i + " ";
                document.getElementById(`tile${Data.unitList[i].x},${Data.unitList[i].y}`).classList.add("selectableUnit");
                    document.getElementById(`tile${Data.unitList[i].x-1},${Data.unitList[i].y+1}`).attributes.units += i + " ";
                }
                if (typeof Data.unitList[i].token === "undefined" || Data.unitList[i].token == "") {
                    tmpSpan = document.createElement("span");
                    tmpSpan.style.color = Data.unitList[i].color;
                    tmpSpan.innerText = Data.unitList[i].charName;
                    document.getElementById(`tile${Data.unitList[i].x},${Data.unitList[i].y}`).appendChild(tmpSpan);
                    if (typeof Data.unitList[i].size !== "undefined" && Data.unitList[i].size == "large") {
                        document.getElementById(`tile${Data.unitList[i].x-1},${Data.unitList[i].y}`).appendChild(tmpSpan);
                        document.getElementById(`tile${Data.unitList[i].x},${Data.unitList[i].y+1}`).appendChild(tmpSpan);
                        document.getElementById(`tile${Data.unitList[i].x-1},${Data.unitList[i].y+1}`).appendChild(tmpSpan);
                    }
                } else {
                    tokenDiv2 = document.createElement("img");
                    tokenDiv2.src = Data.unitList[i].token;
                    tokenDiv2.style.pointerEvents = "none"
                    position_top = Data.unitList[i].x*zoomSize + 4;
                    position_left = Data.unitList[i].y*zoomSize + 4;
                    if (Data.unitList[i].size == "large") {
                        position_top -= zoomSize;
                        tokenDiv2.style.width = zoomSize*2 - 8 + "px";
                        tokenDiv2.style.height = zoomSize*2  - 8+ "px";
                        tokenDiv2.style.position = "absolute";
                    } else {
                        tokenDiv2.style.width = zoomSize - 8 + "px";
                        tokenDiv2.style.height = zoomSize  - 8 + "px";
                        tokenDiv2.style.position = "absolute";
                    }
                    if (Data.inInit && Data.unitList[i].initNum == Data.initiativeCount) {
                        tokenDiv2.style.borderWidth = "5px";
                        tokenDiv2.style.borderStyle = "solid";
                        tokenDiv2.style.borderImage = "radial-gradient(red, transparent)10";
                        position_top -= 5;
                        position_left -= 5;
                    }
                    tokenDiv2.style.top = position_top + "px";
                    tokenDiv2.style.left = position_left + "px";
                    document.getElementById("mapGraphic").appendChild(tokenDiv2);
                }
            }
        }
        for (var i = 0; i < Data.effects.length; i++) {
            tmpEffect = generateEffect(Data.effects[i].shape, Data.effects[i].size, Data.effects[i].color);
            locateEffect(tmpEffect, Data.effects[i].origin.x, Data.effects[i].origin.y);
        }
        if (Data.inInit) {
            for (i = 0; i<Data.initiativeList[Data.initiativeCount].movePath.length - 1;i++) {
                moveLoc = Data.initiativeList[Data.initiativeCount].movePath[i];
                tmpMovDiv = document.createElement("div");
                tmpMovDiv.classList.add("moveDot");
                tmpMovDiv.style.width = zoomSize/10 + "px";
                tmpMovDiv.style.height = zoomSize/10 + "px";
                tmpMovDiv.style.position = "absolute";
                tmpMovDiv.style.top = moveLoc[0]*zoomSize+zoomSize/2.2 + "px";
                tmpMovDiv.style.left = moveLoc[1]*zoomSize+zoomSize/2.2 + "px";
                tmpMovDiv.style.background = Data.initiativeList[Data.initiativeCount].color;
                document.getElementById("mapGraphic").appendChild(tmpMovDiv);
            }
            if (Data.initiativeList[Data.initiativeCount].x != -1) {
                document.getElementById("tile" + Data.initiativeList[Data.initiativeCount].x + "," + Data.initiativeList[Data.initiativeCount].y).style.background = "firebrick";
                if (Data.initiativeList[Data.initiativeCount].size == "large") {
                    document.getElementById("tile" + (Data.initiativeList[Data.initiativeCount].x - 1) + "," + Data.initiativeList[Data.initiativeCount].y).style.background = "firebrick";
                    document.getElementById("tile" + Data.initiativeList[Data.initiativeCount].x + "," + (Data.initiativeList[Data.initiativeCount].y + 1)).style.background = "firebrick";
                    document.getElementById("tile" + (Data.initiativeList[Data.initiativeCount].x - 1) + "," + (Data.initiativeList[Data.initiativeCount].y + 1)).style.background = "firebrick";
                }
            }
            if (typeof selectedUnits !== "undefined") { //selectedUnit
                for (u=0; u> selectedUnits.length; u++){
                    document.getElementById("tile" + Data.unitList[selectedUnits[u]].x + "," + Data.unitList[selectedUnits[u]].y).style.background = "firebrick";
                    if (Data.initiativeList[Data.initiativeCount].size == "large") {
                        document.getElementById("tile" + (Data.unitList[selectedUnits[u]].x - 1) + "," + Data.unitList[selectedUnits[u]].y).style.background = "firebrick";
                        document.getElementById("tile" + Data.unitList[selectedUnits[u]].x + "," + (Data.unitList[selectedUnits[u]].y + 1)).style.background = "firebrick";
                        document.getElementById("tile" + (Data.unitList[selectedUnits[u]].x - 1) + "," + (Data.unitList[selectedUnits[u]].y + 1)).style.background = "firebrick";
                    }
                }
            }
            document.getElementById("movement").innerText = Math.floor(Data.initiativeList[Data.initiativeCount].distance) * 5
        }

        backgroundDiv = document.createElement("div");
        backgroundDiv.style.height = Data.mapArray.length * 70 +"px";
        backgroundDiv.style.width = Data.mapArray[0].length * 70 + "px";
        backgroundDiv.style.position = "absolute";
        backgroundDiv.style.left = "0";
        backgroundDiv.style.top = "0";
        backgroundDiv.style.zIndex = "-1";
        if (defaultBackground) {
            backgroundDiv.style.backgroundImage = "url(static/images/mapbackground.jpg)";
            document.getElementById("mapGraphic").appendChild(backgroundDiv);
        }
    } catch (e) {
        socket.emit("error_handle", room, e);
    }
}*/
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
function get_spells (casterClass, level, callback) {
    socket.emit("database_spells", casterClass, level, callback)
}
function formatSpell(spell, showPrepare) { //probably obsolete
    try {
        //console.log("Warning, using obsolete formatSpell()")
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

function requestImages() {
    socket.emit("request_images", room);
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
        } else if (effect.size == 5) {
            effect.numSquares = 4;
        } else if (effect.size == 10) {
            effect.numSquares = 12;
        } else if (effect.size == 15) {
            effect.numSquares = 24;
        } else if (effect.size == 20) {
            effect.numSquares = 44;
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
    }
    return effect;
}

function deleteEffect(effect) {
    for (i = 0; i< effect.numSquares; i++){
        effect.divs[i].remove();
    }
}

function locateEffect(effect, x, y) {
    if (effect.shape == "circle"){
        effect.origin.x = x;
        effect.origin.y = y;
        if (effect.size == 0) {
            effect.divs[0].style.top = y * 70 + "px";
            effect.divs[0].style.left = x * 70 + "px";
        } else {
            effect.divs[0].style.top = y * 70 + "px";
            effect.divs[0].style.left = x * 70 + "px";

            effect.divs[1].style.top = (y -1) * 70 + "px";
            effect.divs[1].style.left = x * 70 + "px";

            effect.divs[2].style.top = y * 70 + "px";
            effect.divs[2].style.left = (x -1) * 70 + "px";

            effect.divs[3].style.top = (y-1) * 70 + "px";
            effect.divs[3].style.left = (x-1) * 70 + "px";
            if (effect.size > 5) {
                effect.divs[4].style.top = (y+1) * 70 + "px";
                effect.divs[4].style.left = (x) * 70 + "px";

                effect.divs[5].style.top = (y) * 70 + "px";
                effect.divs[5].style.left = (x+1) * 70 + "px";

                effect.divs[6].style.top = (y-1) * 70 + "px";
                effect.divs[6].style.left = (x+1) * 70 + "px";

                effect.divs[7].style.top = (y+1) * 70 + "px";
                effect.divs[7].style.left = (x-1) * 70 + "px";

                effect.divs[8].style.top = (y-2) * 70 + "px";
                effect.divs[8].style.left = (x) * 70 + "px";

                effect.divs[9].style.top = (y) * 70 + "px";
                effect.divs[9].style.left = (x-2) * 70 + "px";

                effect.divs[10].style.top = (y-1) * 70 + "px";
                effect.divs[10].style.left = (x-2) * 70 + "px";

                effect.divs[11].style.top = (y-2) * 70 + "px";
                effect.divs[11].style.left = (x-1) * 70 + "px";
            }
            if (effect.size > 10) {
                effect.divs[12].style.top = (y+1) * 70 + "px";
                effect.divs[12].style.left = (x+1) * 70 + "px";

                effect.divs[13].style.top = (y-2) * 70 + "px";
                effect.divs[13].style.left = (x+1) * 70 + "px";

                effect.divs[14].style.top = (y-2) * 70 + "px";
                effect.divs[14].style.left = (x-2) * 70 + "px";

                effect.divs[15].style.top = (y+1) * 70 + "px";
                effect.divs[15].style.left = (x-2) * 70 + "px";

                effect.divs[16].style.top = (y+2) * 70 + "px";
                effect.divs[16].style.left = (x) * 70 + "px";

                effect.divs[17].style.top = (y) * 70 + "px";
                effect.divs[17].style.left = (x+2) * 70 + "px";

                effect.divs[18].style.top = (y-1) * 70 + "px";
                effect.divs[18].style.left = (x+2) * 70 + "px";

                effect.divs[19].style.top = (y+2) * 70 + "px";
                effect.divs[19].style.left = (x-1) * 70 + "px";

                effect.divs[20].style.top = (y-3) * 70 + "px";
                effect.divs[20].style.left = (x) * 70 + "px";

                effect.divs[21].style.top = (y) * 70 + "px";
                effect.divs[21].style.left = (x-3) * 70 + "px";

                effect.divs[22].style.top = (y-1) * 70 + "px";
                effect.divs[22].style.left = (x-3) * 70 + "px";

                effect.divs[23].style.top = (y-3) * 70 + "px";
                effect.divs[23].style.left = (x-1) * 70 + "px";
            }
            if (effect.size > 15) {
                effect.divs[24].style.top = (y-4) * 70 + "px";
                effect.divs[24].style.left = (x) * 70 + "px";

                effect.divs[25].style.top = (y-3) * 70 + "px";
                effect.divs[25].style.left = (x+1) * 70 + "px";

                effect.divs[26].style.top = (y-3) * 70 + "px";
                effect.divs[26].style.left = (x+2) * 70 + "px";

                effect.divs[27].style.top = (y-2) * 70 + "px";
                effect.divs[27].style.left = (x+2) * 70 + "px";

                effect.divs[28].style.top = (y-1) * 70 + "px";
                effect.divs[28].style.left = (x+3) * 70 + "px";

                effect.divs[29].style.top = (y) * 70 + "px";
                effect.divs[29].style.left = (x+3) * 70 + "px";

                effect.divs[30].style.top = (y+1) * 70 + "px";
                effect.divs[30].style.left = (x+2) * 70 + "px";

                effect.divs[31].style.top = (y+2) * 70 + "px";
                effect.divs[31].style.left = (x+2) * 70 + "px";

                effect.divs[32].style.top = (y+2) * 70 + "px";
                effect.divs[32].style.left = (x+1) * 70 + "px";

                effect.divs[33].style.top = (y+3) * 70 + "px";
                effect.divs[33].style.left = (x) * 70 + "px";

                effect.divs[34].style.top = (y+3) * 70 + "px";
                effect.divs[34].style.left = (x-1) * 70 + "px";

                effect.divs[35].style.top = (y+2) * 70 + "px";
                effect.divs[35].style.left = (x-2) * 70 + "px";

                effect.divs[36].style.top = (y+2) * 70 + "px";
                effect.divs[36].style.left = (x-3) * 70 + "px";

                effect.divs[37].style.top = (y+1) * 70 + "px";
                effect.divs[37].style.left = (x-3) * 70 + "px";

                effect.divs[38].style.top = (y) * 70 + "px";
                effect.divs[38].style.left = (x-4) * 70 + "px";

                effect.divs[39].style.top = (y-1) * 70 + "px";
                effect.divs[39].style.left = (x-4) * 70 + "px";

                effect.divs[40].style.top = (y-2) * 70 + "px";
                effect.divs[40].style.left = (x-3) * 70 + "px";

                effect.divs[41].style.top = (y-3) * 70 + "px";
                effect.divs[41].style.left = (x-3) * 70 + "px";

                effect.divs[42].style.top = (y-3) * 70 + "px";
                effect.divs[42].style.left = (x-2) * 70 + "px";

                effect.divs[43].style.top = (y-4) * 70 + "px";
                effect.divs[43].style.left = (x-1) * 70 + "px";

            }
        }
    }
    if (effect.divs[0].parentNode == null) {
        for (i = 0; i< effect.numSquares; i++){
            document.getElementById("mapGraphic").appendChild(effect.divs[i]);
        }
    }
}

function showEffectControls() { //TODO: add a button to add effect, rather than automatically doing so.
    document.getElementById("activeTabDiv").style.height = "calc(80% - 40px)";
    document.getElementById("bottomDiv").style.display = "block";
    document.getElementById("showEffectDivButton").onclick = hideEffectControls;

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
    document.getElementById("bottomDiv").appendChild(table);

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
        td.innerText = effects[i].duration;
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
    //td.innerText = "test";
    tr.appendChild(td);
    td = document.createElement("td");
    effectShapeSelect = document.createElement("select");
    effectShapeOption = document.createElement("option");
    effectShapeOption.innerText = "Circle";
    effectShapeSelect.appendChild(effectShapeOption);
    /*effectShapeOption = document.createElement("option");
    effectShapeOption.innerText = "Line";
    effectShapeSelect.appendChild(effectShapeOption);*/
    td.appendChild(effectShapeSelect);

    tr.appendChild(td);




    td = document.createElement("td");
    effectSizeSelect = document.createElement("select");
    td.appendChild(effectSizeSelect);
    tr.appendChild(td);

    td = document.createElement("td");
    durationSpinner = document.createElement("select");
    durationOption = document.createElement("option");
    durationOption.innerText = "instantaneous";
    durationSpinner.append(durationOption);
    td.appendChild(durationSpinner);
    tr.appendChild(td);

    td = document.createElement("td");
    colorSelect = document.createElement("select");
    colorSelect.id = "effectColorPicker";
    colorSelect.onchange = function() {deleteEffect(testEffect); testEffect = generateEffect("circle", parseInt(effectSizeSelect.value), colorSelect.value);}
    for (i=0;i<colors.length; i++) {
        colorOption = document.createElement("option");
        colorOption.innerText = colors[i];
        colorOption.style.color = colors[i];
        colorSelect.appendChild(colorOption);
    }
    td.appendChild(colorSelect)
    tr.appendChild(td);

    table.appendChild(tr);
    effectSizeSelect.onchange = function() {deleteEffect(testEffect); testEffect = generateEffect("circle", parseInt(effectSizeSelect.value), colorSelect.value);}
    effectSizeOption = document.createElement("option");
    effectSizeOption.innerText = "0";
    effectSizeSelect.appendChild(effectSizeOption);

    effectSizeOption = document.createElement("option");
    effectSizeOption.innerText = "5";
    effectSizeSelect.appendChild(effectSizeOption);

    effectSizeOption = document.createElement("option");
    effectSizeOption.innerText = "10";
    effectSizeSelect.appendChild(effectSizeOption);

    effectSizeOption = document.createElement("option");
    effectSizeOption.innerText = "15";
    effectSizeSelect.appendChild(effectSizeOption);

    effectSizeOption = document.createElement("option");
    effectSizeOption.innerText = "20";
    effectSizeSelect.appendChild(effectSizeOption);


    tr = document.createElement("tr");
    td = document.createElement("td");
    button = document.createElement("button");
    button.innerText = "Add";
    td.appendChild(button);
    tr.appendChild(td);
    table.appendChild(tr);

    button.onclick = function () {
        document.getElementById("addEffectRow").style.display = "table-row";
        testEffect = generateEffect("circle", 0, "blueviolet");

        document.getElementById("mapContainer").onclick = function(e){
            if (isDragging) {
                return;
            }
            e.preventDefault();
            e.stopPropagation();
            testEffect.title = input.value;
            testEffect.duration = durationSpinner.value;
            updateEffects(true);
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
                if (testEffect.shape == "circle" && testEffect.size == 0) {
                mouseX = Math.floor(mouseX/70)
                mouseY = Math.floor(mouseY/70)
                } else {
                mouseX = Math.round(mouseX/70)
                mouseY = Math.round(mouseY/70)
                }
                locateEffect(testEffect, mouseX, mouseY);
            } catch (e) {
                socket.emit("error_handle", room, e);
            }
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
    /*while (document.getElementById("promptDiv").firstChild) {
        document.getElementById("promptDiv").firstChild.remove();
    }*/
    document.getElementById("effectTable").remove();
    document.getElementById("bottomDiv").style.display = "none";
    document.getElementById("activeTabDiv").style.height = "calc(100% - 40px)";
    document.getElementById("showEffectDivButton").onclick = showEffectControls;



    /*
    var effectCanvas = document.createElement("canvas")
    effectCanvas.style.position = "absolute"
    effectCanvas.style.top = 0
    effectCanvas.style.pointerEvents = "none";
    document.getElementById("mapGraphic").appendChild(effectCanvas);
    effectCanvas.width = playerData.mapArray[0].length*70
    effectCanvas.height = playerData.mapArray.length*70
    var ctx = effectCanvas.getContext("2d");

    document.getElementById("mapContainer").onmousemove = function(e){
        mouseX = (e.clientX)
        mouseX -= document.getElementById("mapContainer").getBoundingClientRect().x
        mouseX += document.getElementById("mapContainer").scrollLeft;
        mouseX /= zoom;

        mouseY = (e.clientY)
        mouseY -= document.getElementById("mapContainer").getBoundingClientRect().y
        mouseY += document.getElementById("mapContainer").scrollTop;
        mouseY /= zoom;

        //need to get the point in the middle of the player. Will simplify for now.
        playerX = playerData.playerList[charName].x * 70 + 35
        playerY = playerData.playerList[charName].y * 70 + 35

        angle = Math.atan2(mouseY - playerX, mouseX - playerY) * 180 / Math.PI;
        newPoint = findNewPoint(playerY, playerX, angle, 70*6);
        ctx.clearRect(0, 0, effectCanvas.width, effectCanvas.height)
        ctx.beginPath();
        ctx.moveTo(playerY, playerX);
        ctx.lineTo(newPoint.x, newPoint.y)
        ctx.lineWidth = 10;
        //console.log(newPoint);
        //console.log (playerY);
        ctx.stroke();
    }*/



}

function findNewPoint(x, y, angle, distance) { //https://stackoverflow.com/questions/17456783/javascript-figure-out-point-y-by-angle-and-distance
    var result = {};

    result.x = Math.round(Math.cos(angle * Math.PI / 180) * distance + x);
    result.y = Math.round(Math.sin(angle * Math.PI / 180) * distance + y);

    return result;
}

function updateEffects(addnew) {
    if (addnew && typeof testEffect !== "undefined"){
        tempEffect = {};
        tempEffect.shape = testEffect.shape;
        tempEffect.size = testEffect.size;
        tempEffect.origin = testEffect.origin;
        tempEffect.title = testEffect.title;
        tempEffect.color = testEffect.color;
        tempEffect.duration = testEffect.duration;
        if (isGM) {
        tempEffect.owner = 0;
        } else {
        tempEffect.owner = charName;
        }
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