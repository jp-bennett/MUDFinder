//var selectedInitiative;
var selectedUnits = [];
var gmData;
var zoomSize = 70;
var selectedTool;
var socket;
var charName = "GM";
var multiSelect = false;
var ds; /* = new DragSelect({
  selectables: document.getElementsByClassName('selectableTile'),
  callback: function(elements) {handleDrag(elements);},
  area: document.getElementById("mapContainer")
});*/
const isGM = true;
showSeenOverlay = true;
mapBackground = "static/images/mapbackground.jpg";
// What .slightlyTransparent is set back to when features are shown. Tiles over
// the default background are drawn a little see-through so the parchment shows
// through them; this has to match the stylesheet.
const SHOWN_TILE_OPACITY = "0.6";


document.getElementById("mapContainer").onwheel = function(e){
    try {
        if (e.ctrlKey || !multiSelect){

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

        /*
            e.preventDefault()
            mouseX = (e.clientX - e.currentTarget.getBoundingClientRect().x + e.currentTarget.scrollLeft) / zoomSize;
            mouseY = (e.clientY - e.currentTarget.getBoundingClientRect().y + e.currentTarget.scrollTop) / zoomSize;
            if (e.deltaY < 0) {
                zoomIn(mouseX, mouseY);
            } else if (e.deltaY > 0) {
                zoomOut(mouseX, mouseY);
            } */
        }
    } catch (e) {
        socket.emit("error_handle", room, e);
    }
}

window.onload = function() {
    try {
        socket = io({path: (typeof SOCKETIO_PATH === "undefined" ? "/socket.io" : SOCKETIO_PATH),
                       transports: ['websocket'], upgrade: false});
    } catch (e) {
        alert("Could not connect to websocket");
    }
    applyFeaturesToggle();
    // On the map itself, not the container: the container also holds mapForm,
    // and swallowing clicks there would disable its buttons while aligning.
    document.getElementById("mapGraphic").addEventListener("mousedown", alignmentDragStart);
    document.getElementById("mapGraphic").addEventListener("click", alignmentSwallowClick, true);
    // Double-click a token for its statblock. The single click is already
    // spoken for by select-and-move, so this needs a gesture of its own.
    document.getElementById("mapGraphic").addEventListener("dblclick", mapDoubleClick);
    window.addEventListener("mousemove", alignmentDragMove);
    window.addEventListener("mouseup", alignmentDragEnd);
    // Shut to start with, and this is also what puts the first handler on the
    // tab: the two functions hand the click back and forth between them, so
    // until one of them has run the tab is a picture of a tab that does
    // nothing. The player view has always called this on load for that reason.
    hideBottomDiv();

    socket.on('connect', function() {
        try {
            //console.log('Websocket connected!');
            if (typeof window.location.search.split("&")[1] != "undefined") {
                gmKey=window.location.search.split("&")[0].split("=")[1];
                room=window.location.search.split("&")[1].split("=")[1];
                socket.emit('join_gm', {room: room, gmKey: gmKey});
                // Built rather than written: the room comes off the query
                // string, so it is whatever was in the address bar.
                drawSessionLinks(document.getElementById("linkDiv"), room);
                socket.emit("get_lore", room);
                //hideBottomDiv();
            }
        } catch (e) {
            socket.emit("error_handle", room, e);
        }
    });

    socket.on('chat', function(msg) {
        try {
            //console.log(msg);
            now = new Date;
            document.getElementById("chatText").innerText += "[" + now.getHours().toString().padStart(2, '0') + ":" + now.getMinutes().toString().padStart(2, '0') +
            ":" + now.getSeconds().toString().padStart(2, '0') + "] " + msg["charName"] + ": " + msg["chat"];
            document.getElementById("chatText").innerHTML += "<br />";
            document.getElementById("chatText").scrollTop = document.getElementById("chatText").scrollHeight;
        } catch (e) {
            socket.emit("error_handle", room, e);
        }
    });
    socket.on('gm_map', function(msg) {
        keepLocalAlignmentIfPending(msg);
        syncFeaturesToMapType(msg.mapBackground);
        drawMap(msg);
        mapObject = msg;
        exitAlignmentIfNothingToAlign();
        refreshAlignmentFields();
        multiSelectToggle(document.getElementById("multiSelect"));
    });
    socket.on('gm_map_update', function(msg) {
        // Read this before updateMap, which now copies the incoming background
        // and alignment into mapObject itself. Comparing afterwards would
        // always find them equal and never notice the map had changed type.
        dropOwnAlignmentEcho(msg);
        previousBackground = mapObject.mapBackground;
        updateMap(msg, mapObject);
        if (typeof msg.mapBackground !== "undefined" && msg.mapBackground != previousBackground) {
            syncFeaturesToMapType(msg.mapBackground);
            reportBattlemapImageState(msg.mapBackground);
            if (currentGridSize().across === 0
                && msg.mapBackground != "static/images/mapbackground.jpg") {
                // An image chosen with no map yet is the start of a battlemap.
                // With a map already up this is the Background button changing
                // the artwork under it, which must not rebuild anything.
                startBattlemapSetup(msg.mapBackground);
            }
        }
        refreshAlignmentFields();
        if (multiSelect)
            ds.addSelectables(document.getElementsByClassName('selectableTile'));
    });
    socket.on('gm_update', function(msg) {
        try {
            gmData = msg;
            document.title = gmData.name
            unitsByUUID = {};
            for (var i = 0; i < msg.unitList.length; i++) {
                unitsByUUID[msg.unitList[i].uuid] = msg.unitList[i];
            }
            effects = gmData.effects;
            drawUnits(gmData);
            if (multiSelect) {
                if (typeof selectedTool !== "undefined") {
                    ds.setSelectables(document.getElementsByClassName('selectableTile'));
                } else {
                    ds.setSelectables(document.getElementsByClassName('selectableUnit'));
                }
            }
            document.getElementById("unitsDiv").innerHTML = "";
            if (document.getElementById("units").style.display == "none"){
                if (typeof selectedUnits[0] !== "undefined") {
                    populateEditChar(gmData, selectedUnits[0])
                } else {
                    populateEditChar(gmData, 0)
                }
            } else if (typeof playerUnitNum !== "undefined"
                       && typeof gmData.unitList[playerUnitNum] !== "undefined") {
                // An open sheet is deliberately not repopulated: it would wipe
                // whatever the GM was half-way through typing into it. The
                // castings are not a field the GM types into, though -- they
                // are a display of what the server holds, and pressing cast is
                // exactly when the sheet is open.
                drawCastings(document.getElementById("unitCastings"),
                             gmData.unitList[playerUnitNum],
                             gmData.unitList[playerUnitNum].unitNum);
                // The token is a display too, and choosing one is likewise
                // done with the sheet open -- the picture is on the sheet and
                // clicking it is how the dialog is opened in the first place.
                drawUnitToken(gmData.unitList[playerUnitNum]);
            }
            // Both lists are built as elements. A creature's name is whatever
            // it was called -- a player types its own, and a GM types a
            // monster's -- so through innerHTML a name is markup, and a name
            // carrying a quote breaks out of the handler it was pasted into.
            for (var i = 0; i < gmData.unitList.length; i++) {
                document.getElementById("unitsDiv").appendChild(
                    gmUnitRow(gmData.unitList[i], i));
            }
            document.getElementById("initiativeDiv").innerHTML = "";
            for (var i = 0; i < gmData.initiativeList.length; i++) {
                document.getElementById("initiativeDiv").appendChild(
                    gmInitiativeRow(gmData.initiativeList[i], i));
            }
            // Initiative controls
            if (gmData.inInit) {
                inInit = true;
                currentRound = gmData.initiativeCount;
                currentInit = gmData.initiativeCount;
                activeInitiative(gmData.initiativeCount)
                document.getElementById("movementButton").style.display = "block";
                document.getElementById("movementDiv").style.display = "block";
                document.getElementById("beginInit").style.display = "none";
                document.getElementById("advanceInit").style.display = "block";
                document.getElementById("endInit").style.display = "block";
            } else {
                inInit = false;
                currentRound = -1;
                currentInit = -1;
                document.getElementById("movementButton").style.display = "none";
                document.getElementById("movementDiv").style.display = "none";
                document.getElementById("advanceInit").style.display = "none";
                document.getElementById("endInit").style.display = "none";
                if (gmData.initiativeList.length > 0) {
                    document.getElementById("beginInit").style.display = "block";
                } else {
                    document.getElementById("beginInit").style.display = "none";
                }
            }
            //populate saved encounters
            document.getElementById("encountersDiv").innerHTML = "";
            for (var i = 0; i < gmData.savedEncounters.length; i++) {
                document.getElementById("encountersDiv").appendChild(
                    savedEncounterRow(gmData.savedEncounters[i]));
            }
            // populate player list
            // This replaces the whole panel, so the heading is built here --
            // anything put in the template is wiped on the first update.
            // Built as elements rather than as markup: a player names
            // themselves, so their name reaches here as untrusted text, and
            // through innerHTML a name with a quote in it becomes script.
            linksDiv = document.getElementById("links");
            linksDiv.innerHTML = "";
            linksHeading = document.createElement("div");
            linksHeading.classList.add("sectionHeading");
            linksHeading.innerText = "Player Links";
            linksDiv.appendChild(linksHeading);
            document.getElementById("connectedPlayers").innerHTML = "";
            document.getElementById("unitControlledBy").innerHTML =  '<option value="gm" selected="selected">gm</option>';
            for (var i = 0; i < Object.keys(gmData.playerList).length; i++) {
                tmpPlayerName = Object.keys(gmData.playerList)[i];

                tmpLinkRow = document.createElement("div");
                tmpLinkRow.classList.add("linkRow");
                tmpPlayerLink = document.createElement("a");
                tmpPlayerLink.href = "player.html?room=" + encodeURIComponent(room) +
                    "&charName=" + encodeURIComponent(tmpPlayerName);
                tmpPlayerLink.innerText = tmpPlayerName;
                tmpLinkRow.appendChild(tmpPlayerLink);
                tmpDeleteButton = document.createElement("button");
                tmpDeleteButton.innerText = "Delete";
                tmpDeleteButton.addEventListener("click", deleteUser.bind(null, tmpPlayerName));
                tmpLinkRow.appendChild(tmpDeleteButton);
                linksDiv.appendChild(tmpLinkRow);

                tmpControlOption = document.createElement("option");
                tmpControlOption.value = tmpPlayerName;
                tmpControlOption.innerText = tmpPlayerName;
                document.getElementById("unitControlledBy").appendChild(tmpControlOption);
                if (gmData.playerList[tmpPlayerName].connected) {
                    tmpConnected = document.getElementById("connectedPlayers");
                    tmpConnected.appendChild(document.createTextNode(tmpPlayerName));
                    tmpConnected.appendChild(document.createElement("br"));
                }
            }
            // Last, so it redraws against the list this update just brought in
            // -- the HP in it is the whole point of having it on screen.
            drawMobPanel(gmData);
            // And after that: opening the panel draws it again, against the
            // same data, so the order only matters for it being drawn once
            // when nothing opened.
            autoShowForGmTurn(gmData);
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
} // end onload
function mapInput() {
    try {
        mapText = document.getElementById('mapText').value;
        socket.emit('map_upload', {mapText: mapText, mapTextType:"csv", discovered: document.getElementById("mapIsDiscovered").checked, gmKey: gmKey, room: room});
    } catch (e) {
        socket.emit("error_handle", room, e);
    }
}
function saveGameInput() {
    try {
        gameObj = JSON.parse(document.getElementById('saveGameText').value);
        //console.log(gameObj);
        socket.emit('game_upload', {saveGame: gameObj, mapTextType:"csv", discovered: document.getElementById("mapIsDiscovered").checked, gmKey: gmKey, room: room});
    } catch (e) {
        socket.emit("error_handle", room, e);
    }
}
function downloadGame() {
    try {
        window.location = "download.html?gmKey=" + gmKey + "&room=" + room;
    } catch (e) {
            socket.emit("error_handle", room, e);
    }
}
function mapGenerate() {
    try {
        mapWidth = parseInt(document.getElementById('mapWidth').value);
        mapHeight = parseInt(document.getElementById('mapHeight').value);
        socket.emit('map_generate', {mapWidth: mapWidth, mapHeight: mapHeight, discovered: document.getElementById("mapIsDiscovered").checked, gmKey: gmKey, room: room});
    } catch (e) {
        socket.emit("error_handle", room, e);
    }
}
function showMapBackgroundSelect() {
}

function reportBattlemapImageState(mapBackground) {
    // Confirmation that the image actually arrived. The server echoing the new
    // background is the only honest evidence of that, so it is said here
    // rather than when the file was handed over.
    state = document.getElementById("battlemapImageState");
    if (!state) {
        return;
    }
    if (mapBackground && mapBackground != "static/images/mapbackground.jpg") {
        state.innerText = "Image loaded. Adjust the grid and the image in the setup bar below the map.";
    } else {
        state.innerText = "No image chosen yet. Choosing one starts the battlemap setup.";
    }
}

var DEFAULT_BATTLEMAP_SQUARES_ACROSS = 20;

function startBattlemapSetup(mapBackground) {
    // Choosing an image on an empty map begins setup rather than asking for a
    // square count first. The count is hard to guess before seeing a grid on
    // the artwork, and it is adjustable throughout setup, so it starts at
    // something reasonable for the image's shape and is corrected by eye.
    try {
        sizingImage = new Image();
        sizingImage.onload = function() {
            across = DEFAULT_BATTLEMAP_SQUARES_ACROSS;
            down = Math.max(1, Math.round(across * sizingImage.naturalHeight / sizingImage.naturalWidth));
            createBattlemapGrid(across, down);
        };
        sizingImage.onerror = function() {
            // The shape is only a starting guess, so a broken preview is no
            // reason to refuse to lay a grid.
            createBattlemapGrid(DEFAULT_BATTLEMAP_SQUARES_ACROSS, DEFAULT_BATTLEMAP_SQUARES_ACROSS);
        };
        sizingImage.src = mapBackground;
    } catch (e) {
        socket.emit("error_handle", room, e);
    }
}

function createBattlemapGrid(across, down) {
    socket.emit('map_generate_over_background', {
        mapWidth: across, mapHeight: down,
        discovered: document.getElementById("mapIsDiscovered").checked,
        gmKey: gmKey, room: room});
    document.getElementById("alignBackground").checked = true;
    alignmentToggle(document.getElementById("alignBackground"));
}

function alignmentResize() {
    // Changing the square count rebuilds the grid, keeping any tiles that are
    // still inside it, so this can be adjusted as freely as the image itself.
    try {
        across = parseInt(document.getElementById("alignGridWidth").value);
        down = parseInt(document.getElementById("alignGridHeight").value);
        if (isNaN(across) || isNaN(down) || across < 1 || down < 1) {
            refreshAlignmentFields();
            return;
        }
        socket.emit('map_resize', {
            mapWidth: across, mapHeight: down,
            discovered: document.getElementById("mapIsDiscovered").checked,
            gmKey: gmKey, room: room});
    } catch (e) {
        socket.emit("error_handle", room, e);
    }
}

function alignmentResizeBy(acrossChange, downChange) {
    try {
        size = currentGridSize();
        document.getElementById("alignGridWidth").value = Math.max(1, size.across + acrossChange);
        document.getElementById("alignGridHeight").value = Math.max(1, size.down + downChange);
        alignmentResize();
    } catch (e) {
        socket.emit("error_handle", room, e);
    }
}

function alignmentFinish() {
    document.getElementById("alignBackground").checked = false;
    alignmentToggle(document.getElementById("alignBackground"));
}

function currentGridSize() {
    if (typeof mapObject === "undefined" || !mapObject || !mapObject.mapArray || !mapObject.mapArray[0]) {
        return {across: 0, down: 0};
    }
    return {across: mapObject.mapArray[0].length, down: mapObject.mapArray.length};
}

var aligningBackground = false;
var alignmentDragFrom = null;

function alignmentToggle(obj) {
    try {
        aligningBackground = obj.checked;
        document.getElementById("alignmentControls").style.display = aligningBackground ? "block" : "none";
        // Over an uploaded image every tile is fullyTransparent, so without
        // this there is no grid on screen to align the artwork against.
        if (aligningBackground) {
            document.getElementById("mapGraphic").classList.add("aligning");
        } else {
            document.getElementById("mapGraphic").classList.remove("aligning");
        }
        // Dragging the image and dragging the view are the same gesture, so
        // only one of them can be live at a time.
        if (aligningBackground) {
            document.getElementById("mapContainer").classList.remove("dragscroll");
        }
        dragscroll.reset();
        refreshAlignmentFields();
    } catch (e) {
        socket.emit("error_handle", room, e);
    }
}

function currentAlignment() {
    // Falls back to the image spanning the grid, which is where a map that has
    // never been aligned effectively sits.
    if (typeof mapObject === "undefined" || !mapObject) {
        return null;
    }
    tilesAcross = (mapObject.mapArray && mapObject.mapArray[0]) ? mapObject.mapArray[0].length : 1;
    return {
        backgroundTilesWide: typeof mapObject.backgroundTilesWide === "number"
            ? mapObject.backgroundTilesWide : tilesAcross,
        backgroundOffsetX: typeof mapObject.backgroundOffsetX === "number" ? mapObject.backgroundOffsetX : 0,
        backgroundOffsetY: typeof mapObject.backgroundOffsetY === "number" ? mapObject.backgroundOffsetY : 0
    };
}

function exitAlignmentIfNothingToAlign() {
    // A map on the default parchment has no uploaded artwork to line up, and
    // leaving the mode on there would strip the tile art off a normal map for
    // no reason.
    if (!aligningBackground || typeof mapObject === "undefined" || !mapObject) {
        return;
    }
    if (mapObject.mapBackground == "static/images/mapbackground.jpg") {
        document.getElementById("alignBackground").checked = false;
        alignmentToggle(document.getElementById("alignBackground"));
    }
}

function setAlignmentField(fieldId, value, places) {
    // Never overwrite the box the GM is typing in. These fields are refreshed
    // on every map update, and a GM part way through typing an offset would
    // otherwise have it replaced mid-keystroke by the value they are editing
    // away from.
    field = document.getElementById(fieldId);
    if (!field || field === document.activeElement) {
        return;
    }
    field.value = value.toFixed(typeof places === "number" ? places : 2);
}

function refreshAlignmentFields() {
    try {
        alignment = currentAlignment();
        if (!alignment || !document.getElementById("alignTilesWide")) {
            return;
        }
        setAlignmentField("alignTilesWide", alignment.backgroundTilesWide);
        setAlignmentField("alignOffsetX", alignment.backgroundOffsetX);
        setAlignmentField("alignOffsetY", alignment.backgroundOffsetY);
        size = currentGridSize();
        setAlignmentField("alignGridWidth", size.across, 0);
        setAlignmentField("alignGridHeight", size.down, 0);
        if (document.getElementById("alignTilesWideSlider") !== document.activeElement) {
            document.getElementById("alignTilesWideSlider").value = alignment.backgroundTilesWide;
        }
    } catch (e) {
        socket.emit("error_handle", room, e);
    }
}

function applyAlignmentLocally(alignment) {
    // Redraw here and tell the server separately, so dragging stays smooth
    // instead of waiting on a round trip for every frame.
    mapObject.backgroundTilesWide = alignment.backgroundTilesWide;
    mapObject.backgroundOffsetX = alignment.backgroundOffsetX;
    mapObject.backgroundOffsetY = alignment.backgroundOffsetY;
    applyMapBackground(mapObject);
    refreshAlignmentFields();
}

// The stamp on the alignment currently shown here. The server raises it on
// every alignment write, so comparing stamps says which of two payloads is
// newer. Kept in step with BACKGROUND_ALIGNMENT_SEQ in session.py.
var ALIGNMENT_SEQ_KEY = "backgroundAlignmentSeq";
var alignmentSeqShown = 0;

function alignmentIsStale(msg) {
    // Whether the alignment in an incoming payload is older than what is
    // already on screen.
    //
    // This used to be a count of our own sends still in flight, which asked
    // the wrong question. The payload that overwrites a drag is usually not an
    // echo of our own change at all: it is a whole map answering an earlier
    // grid resize, carrying the alignment as it stood back then. By the time
    // it arrives our own echo has already been counted off and the guard has
    // stood down, so the stale values land. Compare stamps instead, and it
    // does not matter what prompted the payload or in what order they arrive.
    if (typeof msg[ALIGNMENT_SEQ_KEY] !== "number") {
        // Older servers, and payloads for a map with no alignment at all.
        // Neither can be judged, so neither is treated as stale.
        return false;
    }
    return msg[ALIGNMENT_SEQ_KEY] < alignmentSeqShown;
}

function noteAlignmentSeq(msg) {
    if (typeof msg[ALIGNMENT_SEQ_KEY] === "number" && msg[ALIGNMENT_SEQ_KEY] > alignmentSeqShown) {
        alignmentSeqShown = msg[ALIGNMENT_SEQ_KEY];
    }
}

function dropOwnAlignmentEcho(msg) {
    // Strips the alignment out of an update that is behind what is on screen,
    // so a slow echo of an earlier nudge cannot undo a later one.
    //
    // Returns whether it dropped anything, so this can be checked on its own
    // rather than by trying to lose a race on purpose.
    if (typeof msg.backgroundTilesWide === "undefined") {
        return false;
    }
    if (!alignmentIsStale(msg)) {
        noteAlignmentSeq(msg);
        return false;
    }
    delete msg[ALIGNMENT_SEQ_KEY];
    delete msg.backgroundTilesWide;
    delete msg.backgroundOffsetX;
    delete msg.backgroundOffsetY;
    return true;
}

function keepLocalAlignmentIfPending(msg) {
    // A whole map arriving replaces everything, alignment included. Resizing
    // the grid answers with one, and it carries the alignment as it was when
    // the resize was handled -- which is stale if the image has been adjusted
    // since. Keep the local values on the way in when that is what it is.
    if (typeof mapObject === "undefined" || !mapObject) {
        return;
    }
    if (!alignmentIsStale(msg)) {
        noteAlignmentSeq(msg);
        return;
    }
    for (i = 0; i < BACKGROUND_ALIGNMENT_KEYS.length; i++) {
        if (typeof mapObject[BACKGROUND_ALIGNMENT_KEYS[i]] === "number") {
            msg[BACKGROUND_ALIGNMENT_KEYS[i]] = mapObject[BACKGROUND_ALIGNMENT_KEYS[i]];
        }
    }
    msg[ALIGNMENT_SEQ_KEY] = alignmentSeqShown;
}

function sendAlignment() {
    alignment = currentAlignment();
    if (!alignment) {
        return;
    }
    // Applied locally already. The stamp on the answer will be higher than the
    // one on screen, so the echo is accepted rather than mistaken for stale.
    socket.emit('set_background_alignment', {
        backgroundTilesWide: alignment.backgroundTilesWide,
        backgroundOffsetX: alignment.backgroundOffsetX,
        backgroundOffsetY: alignment.backgroundOffsetY,
        gmKey: gmKey, room: room});
}

function alignmentFieldInput() {
    try {
        alignment = currentAlignment();
        tilesWide = parseFloat(document.getElementById("alignTilesWide").value);
        offsetX = parseFloat(document.getElementById("alignOffsetX").value);
        offsetY = parseFloat(document.getElementById("alignOffsetY").value);
        if (!isNaN(tilesWide) && tilesWide > 0) { alignment.backgroundTilesWide = tilesWide; }
        if (!isNaN(offsetX)) { alignment.backgroundOffsetX = offsetX; }
        if (!isNaN(offsetY)) { alignment.backgroundOffsetY = offsetY; }
        applyAlignmentLocally(alignment);
        sendAlignment();
    } catch (e) {
        socket.emit("error_handle", room, e);
    }
}

function alignmentSliderInput(slider) {
    try {
        alignment = currentAlignment();
        alignment.backgroundTilesWide = parseFloat(slider.value);
        applyAlignmentLocally(alignment);
    } catch (e) {
        socket.emit("error_handle", room, e);
    }
}

function alignmentNudge(field, amount) {
    try {
        alignment = currentAlignment();
        alignment[field] = alignment[field] + amount;
        if (alignment.backgroundTilesWide <= 0) { alignment.backgroundTilesWide = 0.1; }
        applyAlignmentLocally(alignment);
        sendAlignment();
    } catch (e) {
        socket.emit("error_handle", room, e);
    }
}

function alignmentReset() {
    try {
        alignment = currentAlignment();
        alignment.backgroundTilesWide = mapObject.mapArray[0].length;
        alignment.backgroundOffsetX = 0;
        alignment.backgroundOffsetY = 0;
        applyAlignmentLocally(alignment);
        sendAlignment();
    } catch (e) {
        socket.emit("error_handle", room, e);
    }
}

function alignmentDragStart(e) {
    if (!aligningBackground) { return; }
    alignmentDragFrom = {x: e.clientX, y: e.clientY};
    e.preventDefault();
}

function alignmentRound(value) {
    return Math.round(value * 1000) / 1000;
}

function alignmentDragMove(e) {
    if (!aligningBackground || !alignmentDragFrom) { return; }
    // The map is scaled by a CSS transform, so a screen pixel is not a map
    // pixel at any zoom but 1. Divide by the scale, then by the tile size, to
    // land in the grid squares alignment is measured in.
    scale = (typeof zoom === "number" && zoom > 0) ? zoom : 1;
    alignment = currentAlignment();
    // Accumulated raw, and settled once the drag ends. Rounding every step
    // instead makes it worse -- eight small roundings drift further than the
    // float error they were meant to remove.
    alignment.backgroundOffsetX += (e.clientX - alignmentDragFrom.x) / (scale * zoomSize);
    alignment.backgroundOffsetY += (e.clientY - alignmentDragFrom.y) / (scale * zoomSize);
    alignmentDragFrom = {x: e.clientX, y: e.clientY};
    applyAlignmentLocally(alignment);
    e.preventDefault();
}

function alignmentDragEnd() {
    if (!aligningBackground || !alignmentDragFrom) { return; }
    alignmentDragFrom = null;
    // A drag arrives as a run of small moves, and summing the divisions leaves
    // values like 0.9999999999999999 -- which is what the GM then reads in the
    // offset field, and what gets stored and added to again on the next drag.
    // A thousandth of a square is well under a pixel, so nothing is lost.
    alignment = currentAlignment();
    alignment.backgroundOffsetX = alignmentRound(alignment.backgroundOffsetX);
    alignment.backgroundOffsetY = alignmentRound(alignment.backgroundOffsetY);
    alignment.backgroundTilesWide = alignmentRound(alignment.backgroundTilesWide);
    applyAlignmentLocally(alignment);
    sendAlignment();
}

function alignmentSwallowClick(e) {
    // Painting a tile and dragging the image are the same click, so tile edits
    // are held off entirely while aligning.
    if (aligningBackground) {
        e.stopPropagation();
        e.preventDefault();
    }
}
// The first half of a staircase, waiting for the square it joins to. Held
// here rather than on the server: until the second click there is nothing to
// tell anyone about, and a GM who changes their mind should be able to walk
// away from it.
var warpPending = null;

function warpLinkClick(x, y) {
    try {
        if (warpPending === null) {
            warpPending = {x: x, y: y};
            markWarpPending();
            return;
        }
        // The same square twice takes a staircase out, which is also what
        // clicking one that is already joined to something does -- the server
        // lets go of both ends either way.
        socket.emit("link_warp", {
            room: room,
            gmKey: gmKey,
            fromY: warpPending.y,
            fromX: warpPending.x,
            toY: y,
            toX: x,
        });
        clearWarpPending();
    } catch (error) {
        socket.emit("error_handle", room, error);
    }
}

function markWarpPending() {
    var tile = warpPending
        && document.getElementById("tile" + warpPending.x + "," + warpPending.y);
    if (tile) {
        tile.classList.add("warpPending");
    }
}

function clearWarpPending() {
    var marked = document.getElementsByClassName("warpPending");
    while (marked.length > 0) {
        marked[0].classList.remove("warpPending");
    }
    warpPending = null;
}

// One saved encounter, with the button that deletes it.
//
// The name is kept in a data attribute rather than as the element's id. A GM
// types it, so it can be anything -- as an id it broke the attribute it was
// written into, and ids cannot hold a space or a quote in the first place.
function savedEncounterRow(name) {
    var row = document.createElement("div");
    row.dataset.encounter = name;
    row.appendChild(document.createTextNode(name));
    row.addEventListener("click", function () { clickEncounter(row); });
    row.appendChild(rowButton("X", function (e) {
        e.stopPropagation();
        removeEncounter(name);
    }));
    return row;
}

// A small button with a handler bound to it rather than written into an
// attribute. The name in these rows is untrusted, and an attribute is a string
// -- so a name with a quote in it closes the handler and the rest of the name
// runs. Bound, there is no string for it to close.
function rowButton(label, handler) {
    var button = document.createElement("button");
    button.innerText = label;
    button.addEventListener("click", handler);
    return button;
}

// One creature in the GM's list of everything on the board.
function gmUnitRow(unit, index) {
    var row = document.createElement("div");
    row.style.display = "flex";

    var entry = document.createElement("div");
    entry.className = "unitListEntry";
    if (selectedUnits.includes(index)) {
        entry.classList.add("selected");
    }
    entry.style.width = "100%";
    entry.addEventListener("click", function (e) { selectUnit(e, index); });

    var name = document.createElement("div");
    name.style.cssFloat = "left";
    name.style.padding = "7px";
    name.innerText = unit.charName;
    entry.appendChild(name);

    var buttons = document.createElement("div");
    buttons.style.cssFloat = "right";
    if (unit.type !== "player" && !unit.inInit) {
        buttons.appendChild(rowButton("Remove", function (e) { removeUnit(e, index); }));
    }
    buttons.appendChild(rowButton("Info", function (e) {
        showUnitInfoEvent(e, unit.unitNum);
    }));
    entry.appendChild(buttons);

    row.appendChild(entry);
    return row;
}

// One creature in the initiative order, with its HP, the box for changing it,
// and the buttons that move it about.
function gmInitiativeRow(unit, index) {
    var row = document.createElement("div");
    row.style.display = "flex";

    var entry = document.createElement("div");
    entry.className = "InitEntry";
    entry.addEventListener("click", function () { selectInitiative(index); });

    var name = document.createElement("div");
    name.style.textAlign = "center";
    name.style.padding = "7px";
    name.innerText = unit.charName;
    entry.appendChild(name);

    var hp = document.createElement("div");
    hp.style.cssFloat = "left";
    hp.style.padding = "7px";
    hp.innerText = (unit.HP != null) ? unit.HP + "/" + unit.maxHP : "";
    entry.appendChild(hp);

    var changeCell = document.createElement("div");
    changeCell.style.cssFloat = "left";
    changeCell.style.padding = "6px";
    var form = document.createElement("form");
    form.addEventListener("submit", function (e) {
        e.preventDefault();
        changeHP(index);
    });
    var change = document.createElement("input");
    change.type = "text";
    change.id = "hpChange" + index;
    change.style.width = "25px";
    change.addEventListener("click", function (e) { e.stopPropagation(); });
    form.appendChild(change);
    changeCell.appendChild(form);
    entry.appendChild(changeCell);

    var right = document.createElement("div");
    right.style.cssFloat = "right";
    right.style.width = "120px";
    right.appendChild(document.createTextNode("  " + unit.initiative + " "));
    right.appendChild(rowButton("Rem", function (e) { removeInit(e, index); }));
    if (unit.type !== "player") {
        right.appendChild(rowButton("Del", function (e) { delInit(e, index); }));
    }
    right.appendChild(rowButton("Info", function (e) {
        showUnitInfoEvent(e, unit.unitNum);
    }));
    entry.appendChild(right);

    var nudge = document.createElement("div");
    nudge.style.cssFloat = "right";
    var up = document.createElement("span");
    up.style.cursor = "default";
    up.innerText = "▲";
    up.addEventListener("click", function (e) { earlierInit(e, index); });
    var down = document.createElement("span");
    down.style.cursor = "default";
    down.innerText = "▼";
    down.addEventListener("click", function (e) { laterInit(e, index); });
    nudge.appendChild(up);
    nudge.appendChild(document.createElement("br"));
    nudge.appendChild(down);
    entry.appendChild(nudge);

    row.appendChild(entry);
    return row;
}

// The two links a GM hands out. The room is read off this page's own query
// string, so it is whatever was in the address bar -- built as elements, and
// with the room encoded into the URL rather than pasted into it.
function drawSessionLinks(container, roomName) {
    removeContents(container);
    container.appendChild(document.createTextNode("New session created! "));
    var lines = [
        ["Players can use ", "player.html"],
        ["Spectators can use ", "spectator.html"],
    ];
    for (var l = 0; l < lines.length; l++) {
        if (l > 0) {
            container.appendChild(document.createElement("br"));
        }
        container.appendChild(document.createTextNode(lines[l][0]));
        var link = document.createElement("a");
        link.href = lines[l][1] + "?room=" + encodeURIComponent(roomName);
        link.innerText = "this link!";
        container.appendChild(link);
    }
}

function mapTool(e, tileName) {
    try {
        // Changing tool, or putting the same one down, abandons a half-made
        // staircase rather than leaving it to pair with whatever is clicked
        // next.
        clearWarpPending();
        if (typeof selectedTool !== "undefined" && selectedTool == e.target) {
            //ds.setSelectables(undefined, true, false);
            if (multiSelect) {
                ds.setSelectables(document.getElementsByClassName('selectableUnit'));
            }
            deselectAll();
            return;
        }
        deselectAll();
        if (multiSelect) {
            ds.setSelectables(document.getElementsByClassName('selectableTile'));
        }
        e.target.parentElement.classList.add("selected");
        selectedTool = e.target;
    } catch (error) {
        socket.emit("error_handle", room, error);
    }
}

function seenOverlayToggle(obj) {
    try {
        //console.log(obj);
        if(obj.checked) {
            showSeenOverlay = true;
        } else {
            showSeenOverlay = false;
        }
        drawMap(mapObject);
        drawUnits(gmData);

    } catch (e) {
        socket.emit("error_handle", room, e);
    }
}

function featuresToggle(obj) {
    try {
        //console.log(obj);
        // Both transparency classes have to move together. A tile carries
        // slightlyTransparent over the default background and fullyTransparent
        // over an uploaded map image, so driving only one of them left the
        // toggle doing nothing at all on generated maps.
        if(obj.checked) {
            css_getclass(".fullyTransparent").style.opacity = "";
            css_getclass(".slightlyTransparent").style.opacity = SHOWN_TILE_OPACITY;
            if (document.getElementById("mapBackgroundDiv")) {
                document.getElementById("mapBackgroundDiv").style.opacity = .7
            }
            //css_getclass(".floorTile").style.background = "";
        } else {
            css_getclass(".fullyTransparent").style.opacity = "0";
            css_getclass(".slightlyTransparent").style.opacity = "0";
            if (document.getElementById("mapBackgroundDiv")) {
                document.getElementById("mapBackgroundDiv").style.opacity = ""
            }
            //css_getclass(".floorTile").style.background = "white";
        }
        //drawMap(mapObject);
        //drawUnits(gmData);

    } catch (e) {
        socket.emit("error_handle", room, e);
    }
}

function applyFeaturesToggle() {
    // The stylesheet's own values are the two classes' shown/hidden states
    // rather than a single consistent one, so the checkbox is applied on load
    // to put both of them into whichever state it is actually in.
    featuresToggle(document.getElementById("showFeatures"));
}

var featuresMatchDefaultBackground = null;

function syncFeaturesToMapType(mapBackground) {
    // The useful default differs by map. On a generated map the drawn features
    // are the map, so they have to be on. Over an uploaded image they are a
    // grid drawn on top of artwork the GM chose to look at, so they start off,
    // which is how this behaved before the toggle reached generated maps.
    //
    // This only fires when the map changes from one kind to the other, so a GM
    // who sets the checkbox themselves keeps that until they load a different
    // sort of map.
    usingDefaultBackground = (mapBackground == "static/images/mapbackground.jpg");
    if (usingDefaultBackground === featuresMatchDefaultBackground) {
        return;
    }
    featuresMatchDefaultBackground = usingDefaultBackground;
    document.getElementById("showFeatures").checked = usingDefaultBackground;
    applyFeaturesToggle();
}

function sendChat() {
    try {
        socket.emit('chat', {chat: document.getElementById('newChat').value, charName: "gm", gmKey: gmKey, room: room});
        document.getElementById('newChat').value = "";
    } catch (e) {
        socket.emit("error_handle", room, e);
    }
}

function sendMessage() {
    try {
        //console.log('Sending...');
        //console.log(room);
        socket.emit('chat', {chat: document.getElementById("message").value, room: room});
    } catch (e) {
        socket.emit("error_handle", room, e);
    }
}

function requestInit() {
    try {
        //console.log('requesting initiative');
        socket.emit('request_init', {gmKey: gmKey, room: room});
    } catch (e) {
        socket.emit("error_handle", room, e);
    }
}

function unitCount() {
    // A blank or unreadable box means the one creature the form used to add.
    var typed = parseInt(document.getElementById("unitCount").value, 10);
    if (isNaN(typed) || typed < 1) {
        return 1;
    }
    return typed;
}

function refreshInitiativeLabel() {
    // The same box, but adding several creatures at once it holds the modifier
    // they each roll against rather than a count they would all share. A
    // creature out of the bestiary is a modifier however many are being added,
    // because that is what its statblock gives.
    var rolled = unitCount() > 1 || Boolean(chosenCreature);
    document.getElementById("unitInitLabel").innerText =
        rolled ? "Initiative Bonus (d20 rolled for each)" : "Initiative Count";
}

function previewUnitToken() {
    // The field holds either a link or, once a file has been chosen, the whole
    // image as a data URI. Neither is worth reading, so show the picture.
    var value = document.getElementById("unitToken").value;
    var preview = document.getElementById("unitTokenPreview");
    if (value) {
        preview.src = value;
        preview.style.display = "inline-block";
    } else {
        // Removed rather than blanked: an empty src is a request for the page
        // itself in some browsers.
        preview.removeAttribute("src");
        preview.style.display = "none";
    }
}

function chooseUnitToken() {
    try {
        // Returned rather than attached to anything: the creatures this token
        // belongs to do not exist yet, and an image stored before they do
        // would be pruned as unused by the next upload.
        imageUploadReturning("unitTokenField", function (image) {
            document.getElementById("unitToken").value = image;
            previewUnitToken();
        });
    } catch (e) {
        socket.emit("error_handle", room, e);
    }
}

// The statblock behind whatever is in the form, when it came out of the
// bestiary. Everything the GM can see stays editable in the form; this carries
// the rest -- ability scores, senses, DR -- through to the unit.
var chosenCreature;

function clearChosenCreature() {
    // Detaching is a button rather than something that happens when the name is
    // edited: renaming a monster and keeping its statblock is a reasonable
    // thing to want, and losing the statblock silently would not be obvious.
    chosenCreature = undefined;
    document.getElementById("chosenCreature").innerText = "";
    document.getElementById("clearCreatureButton").style.display = "none";
    refreshInitiativeLabel();
}

async function chooseMonster() {
    try {
        var chosen = await chooseCreature();
        if (!chosen) {
            return;
        }
        chosenCreature = chosen;
        // Only the fields the GM might want to overrule are put in the form.
        // The initiative box takes the creature's modifier, because a bestiary
        // entry has one of those and never a finished count.
        document.getElementById("unitName").value = chosen.unit.charName;
        document.getElementById("unitHP").value = chosen.unit.HP;
        document.getElementById("unitInit").value =
            (chosen.initiativeBonus >= 0 ? "+" : "") + chosen.initiativeBonus;
        document.getElementById("chosenCreature").innerText =
            chosen.creature.Name + " — CR " + chosen.creature.CR + ", " + chosen.creature.Size
            + " " + chosen.creature.TypeNorm;
        document.getElementById("clearCreatureButton").style.display = "";
        refreshInitiativeLabel();
        document.getElementById("unitCount").focus();
        document.getElementById("unitCount").select();
    } catch (e) {
        socket.emit("error_handle", room, e);
    }
}

function addUnit() {
    try {
        // A creature from the bestiary brings the fields the form has no boxes
        // for. The form still wins wherever the two overlap, so editing the
        // name or the HP after choosing does what it looks like it does.
        var unit = chosenCreature ? Object.assign({}, chosenCreature.unit) : {};
        unit.charName = document.getElementById("unitName").value;
        unit.token = document.getElementById("unitToken").value;
        unit.charShortName = document.getElementById("unitShortName").value;
        unit.controlledBy = document.getElementById("unitControlledBy").value;
        unit.color = document.getElementById("unitColor").value;
        unit.type = document.getElementById("unitType").value;
        unit.HP = parseInt(document.getElementById("unitHP").value);
        unit.maxHP = unit.HP;
        var count = unitCount();
        var typedInitiative = document.getElementById("unitInit").value;
        // A creature out of the database carries a modifier, so it is rolled
        // even for a single copy. Typed in by hand, one creature still means an
        // exact initiative count and several mean a modifier.
        var rollInitiative = Boolean(chosenCreature) || count > 1;
        unit.initiative = rollInitiative ? 0 : typedInitiative;
        socket.emit('add_units', {
            addToInitiative: document.getElementById("addToInit").checked,
            unit: unit,
            count: count,
            initiativeBonus: rollInitiative ? typedInitiative : 0,
            rollInitiative: rollInitiative,
            room: room,
            gmKey: gmKey,
        });
        document.getElementById("unitName").value = "";
        document.getElementById("unitName").focus();
        document.getElementById("unitShortName").value = "";
        document.getElementById("unitInit").value = "";
        document.getElementById("unitToken").value = "";
        document.getElementById("unitCount").value = "1";
        document.getElementById("unitHP").value = "";
        clearChosenCreature();
        previewUnitToken();
        refreshInitiativeLabel();
    } catch (e) {
        socket.emit("error_handle", room, e);
    }
}

function cssrules() {
    try {
        var rules = {};
        for (var i=0; i<document.styleSheets.length; ++i) {
            var cssRules = document.styleSheets[i].cssRules;
            for (var j=0; j<cssRules.length; ++j)
                rules[cssRules[j].selectorText] = cssRules[j];
        }
        return rules;
    } catch (e) {
        socket.emit("error_handle", room, e);
    }
}

function css_getclass(name) {
    try {
        var rules = cssrules();
        if (!rules.hasOwnProperty(name))
            throw 'TODO: deal_with_notfound_case';
        return rules[name];
    } catch (e) {
        socket.emit("error_handle", room, e);
    }
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
    // The name is on the row as data rather than as its id: a GM types it, and
    // an id cannot hold a space or a quote.
    socket.emit('load_encounter', {clearLocations: document.getElementById("clearLocations").checked, encounterName: document.getElementsByClassName("selectedEncounter")[0].dataset.encounter, room: room, gmKey: gmKey});
}
function clearMap() {
    socket.emit('clear_map', {clearLocations: document.getElementById("clearLocations").checked, room: room, gmKey: gmKey});
}

function removeEncounter(encounterName) {
    socket.emit('remove_encounter', {encounterName: encounterName, room: room, gmKey: gmKey});
}
function clickEncounter(ob) {
    try {
        tmpEncounters = document.getElementById("encountersDiv").children;
        for(var i = 0; i < tmpEncounters.length; i++){
            tmpEncounters[i].className = "";
        }
        ob.className = "selectedEncounter";
    } catch (e) {
        socket.emit("error_handle", room, e);
    }
}
function removeInit(e, initCount) {
    try {
        e.stopPropagation();
        socket.emit('remove_init', {initCount: initCount, room: room, gmKey: gmKey});
    } catch (error) {
        socket.emit("error_handle", room, error);
    }
}
function removeUnit(e, unitCount) {
    try {
        e.stopPropagation();
        socket.emit('remove_unit', {unitCount: unitCount, room: room, gmKey: gmKey});
    } catch (error) {
        socket.emit("error_handle", room, error);
    }
}
function delInit(e, initCount) {
    try {
        e.stopPropagation();
        socket.emit('del_init', {initCount: initCount, room: room, gmKey: gmKey});
    } catch (error) {
        socket.emit("error_handle", room, error);
    }
}

function mapClick(e, x, y) {
    try {
        if (isDragging) {
            isDragging = false;
            e.stopPropagation()
            return;
        }
        if (typeof testEffect !== "undefined"){
            return;
        }
        relative_y = e.offsetY * 16 / zoomSize;
        relative_x = e.offsetX * 16 / zoomSize;
        if (typeof selectedTool !== "undefined") {
            // The link tool needs two squares before it has anything to say,
            // so it is not a paint like the rest of the palette.
            if (selectedTool.id === "warpLink") {
                warpLinkClick(x, y);
                return;
            }
            tiles = [{newTile: selectedTool.id, xCoord: x, yCoord: y}]
            socket.emit('map_edit', {tiles: tiles, room: room, gmKey: gmKey, relative_x: relative_x, relative_y: relative_y});
            return;
        }
        if (e.currentTarget.attributes.units != ""){
            i = parseInt(e.currentTarget.attributes.units.split(" ")[0]);
            selectUnit(e, i)
            return;
        }
        if (typeof selectedUnits[0] !== "undefined" && !e.shiftKey) {
            socket.emit('locate_unit', {selectedUnit: selectedUnits[0], moveType: document.getElementById("movementSelector").selectedIndex, xCoord: x, yCoord: y, relative_x: relative_x, relative_y: relative_y, room: room, gmKey: gmKey});
        } else {
            if (gmData.inInit && gmData.initiativeList[gmData.initiativeCount].controlledBy == "gm") {
                socket.emit('locate_unit', {selectedInit: gmData.initiativeCount, moveType: document.getElementById("movementSelector").selectedIndex, xCoord: x, yCoord: y, relative_x: relative_x, relative_y: relative_y, room: room, gmKey: gmKey});
            }
        }
        if (!e.shiftKey) {
            deselectAll()
            populateEditChar(gmData,0);
        }
    } catch (error) {
        socket.emit("error_handle", room, error);
    }
}

function changeHP(initnum) {
    socket.emit('change_hp', {changeHP: document.getElementById(`hpChange${initnum}`).value, room: room, gmKey: gmKey, initCount: initnum});
}

function selectInitiative(initiativeNum) {
    try {
        selectUnit([], gmData.initiativeList[initiativeNum].unitNum)
    } catch (e) {
        socket.emit("error_handle", room, e);
    }
}

function mapDoubleClick(e) {
    // One listener on the map rather than a handler per square: a battlemap
    // is several hundred tiles and every one of them is rebuilt on redraw.
    try {
        var tile = e.target.closest(".mapTile");
        if (tile === null || tile.attributes.units == "") {
            return;
        }
        e.stopPropagation();
        // The tile records positions in unitList, not unit numbers.
        var onTile = parseInt(tile.attributes.units.split(" ")[0]);
        showUnitInfo(gmData.unitList[onTile].unitNum);
    } catch (error) {
        socket.emit("error_handle", room, error);
    }
}

function showUnitInfo(unitNum) {
    // Select the unit, open the tab its sheet is on, and let populateEditChar
    // draw it. The statblock lives in one place; the buttons on the creature
    // list, the initiative order and the map are all just routes to it.
    //
    // Takes a unitNum rather than a position in unitList, because the
    // initiative order is in its own order and only the number is common to
    // both lists.
    try {
        if (typeof gmData === "undefined" || !gmData) {
            return;
        }
        var index = -1;
        for (var u = 0; u < gmData.unitList.length; u++) {
            if (gmData.unitList[u].unitNum == unitNum) {
                index = u;
                break;
            }
        }
        if (index < 0) {
            return;
        }
        selectedTool = undefined;
        selectedUnits = [index];
        enableTab("units");
        populateEditChar(gmData, unitNum);
        drawMobPanel(gmData);
        document.getElementById("unitStatblock").scrollIntoView({block: "nearest"});
    } catch (e) {
        socket.emit("error_handle", room, e);
    }
}

function showUnitInfoEvent(e, unitNum) {
    // The row underneath selects the unit for the map; this must not do that
    // as well.
    e.stopPropagation();
    showUnitInfo(unitNum);
}

function selectUnit(e, unitNum) {
    try {
        selectedTool = undefined;
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
        if (typeof selectedUnits[0] !== "undefined") {
            populateEditChar(gmData, selectedUnits[0]);
        } else {
            populateEditChar(gmData, 0);
        }
        drawMobPanel(gmData);
        drawSelected(gmData);
    } catch (e) {
        socket.emit("error_handle", room, e);
    }
}

function activeInitiative(initiativeNum) {
    try {
        document.getElementById("initiativeDiv").children[initiativeNum].classList.add("activeUnit");
    } catch (e) {
        socket.emit("error_handle", room, e);
    }
}

// Which creature the panel under the map is about: what the GM has selected,
// and failing that whoever's turn it is. Selection wins so the GM can read one
// creature's attacks while another is up, which is most of what looking at a
// statblock mid-combat is for.
//
// selectedUnits holds indices into unitList; unitNum is that same index, kept
// so by number_units() on the server after every change to the list.
function mobPanelSubject(Data) {
    if (!Data || !Data.unitList || Data.unitList.length === 0) {
        return null;
    }
    if (typeof selectedUnits[0] !== "undefined") {
        for (var s = 0; s < Data.unitList.length; s++) {
            if (Data.unitList[s].unitNum == selectedUnits[0]) {
                return Data.unitList[s];
            }
        }
    }
    if (Data.inInit && Data.initiativeList && Data.initiativeList.length > 0) {
        var current = Data.initiativeList[Data.initiativeCount];
        if (current) {
            // The initiative list carries its own copies, so the unit is looked
            // up by uuid -- its HP there can be a round out of date.
            for (var i = 0; i < Data.unitList.length; i++) {
                if (Data.unitList[i].uuid === current.uuid) {
                    return Data.unitList[i];
                }
            }
            return current;
        }
    }
    return null;
}

// HP, AC and initiative -- the three the GM reaches for every round. HP comes
// off the unit, which is where damage is tracked. A unit carries AC only as the
// pieces it is added up from, so for a creature out of the bestiary it is read
// from the cached record instead, and for one made by hand it stays blank
// rather than showing a wrong total.
function drawMobStats(container, unit) {
    removeContents(container);
    if (!unit) {
        return;
    }
    var hp = (unit.HP === "" || unit.HP === null || typeof unit.HP === "undefined")
        ? "" : String(unit.HP);
    if (hp !== "" && unit.maxHP !== "" && unit.maxHP !== null
        && typeof unit.maxHP !== "undefined") {
        hp += " / " + unit.maxHP;
    }
    mobStat(container, "HP", hp);
    var ac = mobStat(container, "AC", "");
    mobStat(container, "Init", (unit.initiative === "" || unit.initiative === null)
        ? "" : String(unit.initiative));

    // The saves sit at the end of the strip as buttons rather than figures,
    // because a save is a thing the GM does rather than a thing they read.
    var saves = document.createElement("div");
    saves.className = "mobStat mobSaves";
    var savesLabel = document.createElement("span");
    savesLabel.className = "mobStatLabel";
    savesLabel.innerText = "Saves";
    saves.appendChild(savesLabel);
    container.appendChild(saves);

    if (unit.creatureId) {
        var wanted = String(unit.creatureId);
        container.dataset.creatureId = wanted;
        fetchCreatureCached(unit.creatureId).then(function (full) {
            // A different creature may have been picked while this was in
            // flight.
            if (container.dataset.creatureId !== wanted || !full) {
                return;
            }
            ac.innerText = statblockValue(full.creature, ["AC", "AC_Mods"]);
            drawSaveButtons(saves, unit.charName,
                            statblockValue(full.creature, ["Saves", "Save_Mods"]));
        });
    } else {
        container.dataset.creatureId = "";
        // Made by hand, so there is nothing to roll against.
        var none = document.createElement("span");
        none.className = "mobStatValue mobStatNone";
        none.innerText = "—";
        none.title = "not from the bestiary, so no saves are recorded";
        saves.appendChild(none);
    }
}

// One button per save the creature actually has. A save that is not written
// down gets no button rather than a +0 one, which would be a roll that means
// nothing.
function drawSaveButtons(container, who, text) {
    var saves = parseSaves(text);
    var drawn = 0;
    for (var s = 0; s < SAVE_ORDER.length; s++) {
        var save = SAVE_ORDER[s];
        if (typeof saves[save] === "undefined") {
            continue;
        }
        container.appendChild(saveButton(who, save, saves[save]));
        drawn += 1;
    }
    if (drawn === 0) {
        var none = document.createElement("span");
        none.className = "mobStatValue mobStatNone";
        none.innerText = "—";
        none.title = "none recorded for this creature";
        container.appendChild(none);
    }
}

// One "LABEL value" pair in the strip. Returns the value node so a figure that
// has to be fetched can be filled in when it arrives.
function mobStat(container, label, value) {
    var stat = document.createElement("div");
    stat.className = "mobStat";
    var name = document.createElement("span");
    name.className = "mobStatLabel";
    name.innerText = label;
    stat.appendChild(name);
    var figure = document.createElement("span");
    figure.className = "mobStatValue";
    figure.innerText = value;
    stat.appendChild(figure);
    container.appendChild(stat);
    return figure;
}

// The creature's special abilities, folded away behind the button in the
// heading. Everything a GM reaches for in a round is on the panel already; this
// is the rest of the entry -- auras, breath weapons, the DCs -- for when the
// creature actually uses one.
function drawMobAbilities(container, unit) {
    var button = document.getElementById("mobPanelAbilitiesButton");
    var wanted = (unit && unit.creatureId) ? String(unit.creatureId) : "";
    // Same reason drawStatblock guards: this runs on every update from the
    // server, and repainting would throw away wherever the GM had scrolled to.
    if (container.dataset.creatureId === wanted && container.firstChild) {
        return;
    }
    container.dataset.creatureId = wanted;
    removeContents(container);
    if (!wanted) {
        // Made by hand, or a player's own character.
        button.disabled = true;
        button.title = "not from the bestiary, so there is nothing recorded";
        return;
    }
    button.disabled = true;
    button.title = "looking it up";
    fetchCreatureCached(unit.creatureId).then(function (full) {
        if (container.dataset.creatureId !== wanted) {
            return;
        }
        var abilities = full && full.creature && full.creature.SpecialAbilities;
        if (!abilities || !String(abilities).trim()) {
            button.disabled = true;
            button.title = "this one has none recorded";
            return;
        }
        specialAbilityLines(container, abilities);
        button.disabled = false;
        button.title = "";
    });
}

function toggleMobAbilities() {
    try {
        var abilities = document.getElementById("mobPanelAbilities");
        if (abilities.style.display === "none") {
            abilities.style.display = "block";
            document.getElementById("mobPanelAbilitiesButton").classList.add("mobAbilitiesShowing");
        } else {
            hideMobAbilities();
        }
    } catch (e) {
        socket.emit("error_handle", room, e);
    }
}

// The panel has three heights, and the tabs on its edge are how you move
// between them: shut, a quarter of the window, and the whole of it with the map
// behind. A quarter is enough to run a turn from -- the attacks and the HP --
// and not enough to read a caster's spell list in, which is what the full
// height is for.
//
// Shut there is one tab and it opens the panel. Open there are two: one shuts
// it, one takes it full height. Full height there is one again, and it drops
// back to the quarter rather than shutting, so no tab ever skips a step.
function setMobPanelHeight(state) {
    var panel = document.getElementById("bottomDiv");
    var holder = document.getElementById("activeTabDiv");
    var shutTab = document.getElementById("bottomPopupButton");
    var growTab = document.getElementById("bottomExpandButton");
    if (!panel || !shutTab) {
        return;
    }
    var open = state !== "shut";
    var tall = state === "full";

    panel.style.display = open ? "block" : "none";
    panel.classList.toggle("mobPanelTall", tall);
    // The holder gives up its bottom quarter at half height. At full height the
    // panel covers it instead, and the class also puts the holder in a stacking
    // context of its own so the palette inside it stops painting through.
    holder.classList.toggle("mobPanelOpen", state === "half");
    holder.classList.toggle("mobPanelTall", tall);

    // The tabs ride on the panel's top edge, wherever that is.
    shutTab.classList.toggle("panelOpen", open);
    shutTab.classList.toggle("mobPanelTall", tall);
    growTab.classList.toggle("panelOpen", open);

    // Only at half height are there two, since that is the only state with a
    // step in both directions. Spelled out rather than cleared to "": the
    // stylesheet starts this tab hidden, so an empty value would fall back to
    // that and the tab would never appear.
    growTab.style.display = (state === "half") ? "flex" : "none";
    growTab.onclick = function () { expandBottomDiv(); };

    if (state === "shut") {
        shutTab.children[0].src = "static/images/up.svg";
        shutTab.onclick = function () { showBottomDiv(); };
        shutTab.title = "Show the creature panel";
    } else if (state === "half") {
        shutTab.children[0].src = "static/images/down.svg";
        shutTab.onclick = function () { hideBottomDiv(); };
        shutTab.title = "Hide the creature panel";
    } else {
        shutTab.children[0].src = "static/images/down.svg";
        shutTab.onclick = function () { showBottomDiv(); };
        shutTab.title = "Give the map back its room";
    }
}

function expandBottomDiv() {
    try {
        setMobPanelHeight("full");
        drawMobPanel(gmData);
    } catch (e) {
        socket.emit("error_handle", room, e);
    }
}

function hideMobAbilities() {
    document.getElementById("mobPanelAbilities").style.display = "none";
    document.getElementById("mobPanelAbilitiesButton").classList.remove("mobAbilitiesShowing");
}

// Whether the map is the tab on screen. enableTab writes display on each tab,
// and the map's is the only one the creature panel belongs to.
function mapTabIsUp() {
    var map = document.getElementById("mapWrapper");
    return !!map && map.style.display !== "none";
}

// Whose turn the panel last opened itself for. Kept so that it opens once when
// initiative reaches a creature rather than on every update -- a GM who shuts
// it mid-turn should have it stay shut while units move around, and an update
// arrives every time one does.
var lastAutoShownTurn = null;

// Initiative reaching something the GM is running is exactly when they need
// its attacks, so the panel opens itself rather than waiting to be asked.
// Only for the GM's own creatures: a player's turn is the player's to run, and
// a panel opening on it would be in the way rather than useful.
function autoShowForGmTurn(Data) {
    try {
        if (!Data || !Data.inInit || !Data.initiativeList
                || Data.initiativeList.length === 0) {
            lastAutoShownTurn = null;
            return;
        }
        var current = Data.initiativeList[Data.initiativeCount];
        if (!current) {
            return;
        }
        // Which turn it is, rather than whose: with one creature in the order,
        // advancing wraps straight back to it, and going by the creature alone
        // meant the panel never opened again after the first round.
        var turn = Data.roundCount + ":" + Data.initiativeCount;
        if (turn === lastAutoShownTurn) {
            // Same turn as last time, so whatever the GM has done with the
            // panel since stands.
            return;
        }
        lastAutoShownTurn = turn;
        if (current.controlledBy !== "gm") {
            return;
        }
        // The handle is hidden off the map, so opening the panel there would
        // put a creature over the character sheet with no way to shut it.
        if (!mapTabIsUp()) {
            return;
        }
        showBottomDiv();
    } catch (e) {
        socket.emit("error_handle", room, e);
    }
}

// Redrawn on every update from the server, so this has to be cheap and must not
// throw when the panel is shut -- gm_update runs whether it is open or not.
function drawMobPanel(Data) {
    try {
        var name = document.getElementById("mobPanelName");
        if (!name) {
            return;
        }
        var abilities = document.getElementById("mobPanelAbilities");
        var unit = mobPanelSubject(Data);
        // Folded away again when the panel changes creature, rather than the
        // last one's abilities left lying open over the new one's attacks. Kept
        // as it is otherwise: an update arrives every time anything moves, and
        // shutting it on each one would make it unusable.
        var showing = unit ? (unit.uuid || "") : "";
        if (abilities.dataset.showingFor !== showing) {
            abilities.dataset.showingFor = showing;
            hideMobAbilities();
        }
        if (!unit) {
            name.innerText = "Nothing selected";
            removeContents(document.getElementById("mobPanelStats"));
            removeContents(document.getElementById("mobPanelAttacks"));
            removeContents(document.getElementById("mobPanelCastings"));
            removeContents(abilities);
            abilities.dataset.creatureId = "";
            document.getElementById("mobPanelAbilitiesButton").disabled = true;
            return;
        }
        name.innerText = unit.charName;
        drawMobStats(document.getElementById("mobPanelStats"), unit);
        drawAttacks(document.getElementById("mobPanelAttacks"), unit.weapons, unit.charName);
        drawCastings(document.getElementById("mobPanelCastings"), unit, unit.unitNum);
        drawMobAbilities(abilities, unit);
    } catch (e) {
        socket.emit("error_handle", room, e);
    }
}

function resetMovement() {
    socket.emit('reset_movement', {selectedInit: gmData.initiativeCount, room: room, gmKey: gmKey});
}

function addInit() {
    try {
        if (selectedUnits.length == 0) {return;}
        socket.emit('add_to_initiative', {selectedUnits: selectedUnits, room: room, gmKey: gmKey});
        deselectAll();
    } catch (e) {
        socket.emit("error_handle", room, e);
    }
}

function earlierInit(e, ourInitNum) {
    try {
        e.stopPropagation();
        socket.emit('earlier_initiative', {targetInitiativeCount: ourInitNum, room: room, gmKey: gmKey});
    } catch (error) {
        socket.emit("error_handle", room, error);
    }
}

function laterInit(e, ourInitNum) {
    try {
        e.stopPropagation();
        //console.log(ourInitNum);
        socket.emit('later_initiative', {targetInitiativeCount: ourInitNum, room: room, gmKey: gmKey});
    } catch (error) {
        socket.emit("error_handle", room, error);
    }
}

function updateChar () {
    try {
        player = {};
        player.room = room;
        player.gmKey = gmKey;
        player.unitNum = document.getElementById("editCharNum").innerText;
        //player.token = document.getElementById("charToken").value;
        player.charName = document.getElementById("charactername").innerText;
        player.charShortName = document.getElementById("charShortName").value;
        player.color = document.getElementById("playerColor").value;
        if (player.color == "custom") { player.color = document.getElementById("customColor").value;}
        player.perception = document.getElementById("passivePerception").value;
        player.movementSpeed = document.getElementById("movementSpeed").value;
        player.DEX = document.getElementById("dex").value;
        player.size = document.getElementById("size").value;
        player.darkvision = document.getElementById("darkvision").checked;
        player.lowLight = document.getElementById("lowLight").checked;
        player.trapfinding = document.getElementById("trapfinding").checked;
        player.revealsMap = document.getElementById("revealsMap").checked;
        player.hasted = document.getElementById("hasted").checked;
        player.permanentAbilities = document.getElementById("permanentAbilities").value;
        player.initiative = document.getElementById("init").value
        // The attack rows are editable, so what they hold now is what the unit
        // should keep. Read from the panel rather than from gmData, or a
        // corrected bonus is lost the moment anything else updates.
        player.weapons = readAttacks(document.getElementById("unitAttacks"));
        socket.emit('update_unit', player);
    } catch (e) {
        socket.emit("error_handle", room, e);
    }
}

function removeCharFromMap () {
    try {
        socket.emit('remove_unit_location', room, gmKey, document.getElementById("editCharNum").innerText);
    } catch (e) {
        socket.emit("error_handle", room, e);
    }
}

function handleDrag (elements) {
    try {
        //console.log(elements)
        selectionSize = ds.getCursorPositionDifference();
        if (Math.abs(selectionSize.x) < 10 && Math.abs(selectionSize.y) < 10){
            ds.clearSelection();
            return;
        }
        if (typeof selectedTool !== "undefined") {
            if (elements.length < 2){
                ds.clearSelection();
                return;
            }
            tiles = [];
            for (i=0; i<elements.length; i++) {
                tiles.push({newTile: selectedTool.id, xCoord: parseInt(elements[i].attributes.x), yCoord: parseInt(elements[i].attributes.y)})
            }

            socket.emit('map_edit', {tiles: tiles, room: room, gmKey: gmKey});
            ds.clearSelection();
            return
        } else {
            //deselectAll()
            for (z=0; z<elements.length; z++) {
                i = elements[z].attributes.units.split(" ");
                for (y=0; y<i.length-1; y++) {
                    //document.getElementById("unitsDiv").children[parseInt(i[y])].children[0].className = "selected";
                    selectedUnits.push(parseInt(i[y]));
                }
                populateEditChar(gmData,parseInt(i[0]));
                drawSelected(gmData);
            }
            ds.clearSelection();
        }
    } catch (e) {
        socket.emit("error_handle", room, e);
    }
}

function deleteUser(delUser) {
    try {
        if (confirm("Delete " + delUser + "?")) {
            //console.log("Deleting");
            socket.emit('delete_player', room, gmKey, delUser);
        }
    } catch (e) {
        socket.emit("error_handle", room, e);
    }
}

function multiSelectToggle(element) {
    if (element.checked) {
        ds = new DragSelect({
        selectables: document.getElementsByClassName('selectableTile'),
        callback: function(elements) {handleDrag(elements);},
        area: document.getElementById("mapContainer")
        });
        multiSelect = true;
        document.getElementById("mapContainer").classList.remove("dragscroll");
    } else {
        if (typeof ds !== "undefined")
            ds.stop();
        ds = undefined;
        multiSelect = false;
        if (mapObject.mapArray.length > 0) {
            document.getElementById("mapContainer").classList.add("dragscroll");
        } else {
            document.getElementById("mapContainer").classList.remove("dragscroll");
        }
    }
    dragscroll.reset();

}
// The creature panel under the map, opened and shut by the tab on its top
// edge. The player's action bar works the same way, and this shrinks the same
// holder -- a class rather than a written-in height, so the two numbers that
// have to agree both live in the stylesheet.
function hideBottomDiv() {
    try {
        // Shut is shut from any height. Expanding is done to read something;
        // the panel opens itself when initiative reaches one of the GM's
        // creatures, and having the map disappear at the top of every one of
        // its turns is not what anybody asked for.
        setMobPanelHeight("shut");
    } catch (e) {
        socket.emit("error_handle", room, e);
    }
}

function showBottomDiv() {
    try {
        setMobPanelHeight("half");
        // Opened by hand is exactly when the GM wants to see it filled, and an
        // update may not arrive for a while.
        drawMobPanel(gmData);
    } catch (e) {
        socket.emit("error_handle", room, e);
    }
}