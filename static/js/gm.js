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
        socket = io({transports: ['websocket'], upgrade: false});
    } catch (e) {
        alert("Could not connect to websocket");
    }
    applyFeaturesToggle();
    // On the map itself, not the container: the container also holds mapForm,
    // and swallowing clicks there would disable its buttons while aligning.
    document.getElementById("mapGraphic").addEventListener("mousedown", alignmentDragStart);
    document.getElementById("mapGraphic").addEventListener("click", alignmentSwallowClick, true);
    window.addEventListener("mousemove", alignmentDragMove);
    window.addEventListener("mouseup", alignmentDragEnd);

    socket.on('connect', function() {
        try {
            //console.log('Websocket connected!');
            if (typeof window.location.search.split("&")[1] != "undefined") {
                gmKey=window.location.search.split("&")[0].split("=")[1];
                room=window.location.search.split("&")[1].split("=")[1];
                socket.emit('join_gm', {room: room, gmKey: gmKey});
                document.getElementById("linkDiv").innerHTML = 'New session created!' +
                ` Players can use <a href="player.html?room=${room}">this link!</a><br>` +
                ` Spectators can use <a href="spectator.html?room=${room}">this link!</a>`;
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
            }
            for (var i = 0; i < gmData.unitList.length; i++) {
                tmpUnit = `
                  <div style="display:flex;">
                     <div onclick="selectUnit(event, ${i})" `;
                     tmpUnit += 'class="unitListEntry"'
                       if (selectedUnits.includes(i)) {
                           tmpUnit += 'class=" selected"'
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
                  </div>`;
                document.getElementById("unitsDiv").innerHTML += tmpUnit
            }
            document.getElementById("initiativeDiv").innerHTML = "";
            for (var i = 0; i < gmData.initiativeList.length; i++) {
                tmpHTML = `
                  <div style="display:flex;">
                     <div onclick="selectInitiative(${i})"`;
                     tmpHTML += 'class="InitEntry">';
                      tmpHTML += `<div style="text-align:center; padding:7px;">  ${gmData.initiativeList[i].charName}
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
                  </div>`;
                document.getElementById("initiativeDiv").innerHTML += tmpHTML;
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
                document.getElementById("encountersDiv").innerHTML += `<div onclick="clickEncounter(this)" id="${gmData.savedEncounters[i]}">` +
                gmData.savedEncounters[i] + `<button onclick="removeEncounter('${gmData.savedEncounters[i]}')">X</button></div>`;
            }
            // populate player list
            document.getElementById("links").innerHTML = "Links<br>";
            document.getElementById("connectedPlayers").innerHTML = "";
            document.getElementById("unitControlledBy").innerHTML =  '<option value="gm" selected="selected">gm</option>';
            for (var i = 0; i < Object.keys(gmData.playerList).length; i++) {
                tmpPlayerName = Object.keys(gmData.playerList)[i];
                document.getElementById("links").innerHTML += `<a href="player.html?room=${room}&charName=${tmpPlayerName}">${tmpPlayerName}</a>` +
                    `<button onclick="deleteUser('${tmpPlayerName}')">Delete</button><br>`;
                document.getElementById("unitControlledBy").innerHTML += `<option value="${tmpPlayerName}">${tmpPlayerName}</option>`;
                if (gmData.playerList[tmpPlayerName].connected) {
                    document.getElementById("connectedPlayers").innerHTML += tmpPlayerName + "<br >";
                }
            }
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

var alignmentSendsInFlight = 0;

function dropOwnAlignmentEcho(msg) {
    // Every alignment change is echoed back by the server. An echo of an
    // earlier change can arrive after a later one has been made here, and
    // applying it would undo that: a quick second nudge jumps back to where
    // the first one left it. While any of our own changes are still in flight,
    // strip the alignment out of what arrives and keep the local values.
    //
    // Returns whether it dropped anything, so this can be checked on its own
    // rather than by trying to lose a race on purpose.
    if (typeof msg.backgroundTilesWide === "undefined" || alignmentSendsInFlight < 1) {
        return false;
    }
    alignmentSendsInFlight--;
    delete msg.backgroundTilesWide;
    delete msg.backgroundOffsetX;
    delete msg.backgroundOffsetY;
    return true;
}

function keepLocalAlignmentIfPending(msg) {
    // A whole map arriving replaces everything, alignment included. Resizing
    // the grid answers with one, and it carries the alignment as it was when
    // the resize was handled -- which is stale if the image has been adjusted
    // since. While any of our own alignment changes are still in flight, keep
    // the local values on the way in.
    if (alignmentSendsInFlight < 1 || typeof mapObject === "undefined" || !mapObject) {
        return;
    }
    for (i = 0; i < BACKGROUND_ALIGNMENT_KEYS.length; i++) {
        if (typeof mapObject[BACKGROUND_ALIGNMENT_KEYS[i]] === "number") {
            msg[BACKGROUND_ALIGNMENT_KEYS[i]] = mapObject[BACKGROUND_ALIGNMENT_KEYS[i]];
        }
    }
}

function sendAlignment() {
    alignment = currentAlignment();
    if (!alignment) {
        return;
    }
    alignmentSendsInFlight++;
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

function alignmentDragMove(e) {
    if (!aligningBackground || !alignmentDragFrom) { return; }
    // The map is scaled by a CSS transform, so a screen pixel is not a map
    // pixel at any zoom but 1. Divide by the scale, then by the tile size, to
    // land in the grid squares alignment is measured in.
    scale = (typeof zoom === "number" && zoom > 0) ? zoom : 1;
    alignment = currentAlignment();
    alignment.backgroundOffsetX += (e.clientX - alignmentDragFrom.x) / (scale * zoomSize);
    alignment.backgroundOffsetY += (e.clientY - alignmentDragFrom.y) / (scale * zoomSize);
    alignmentDragFrom = {x: e.clientX, y: e.clientY};
    applyAlignmentLocally(alignment);
    e.preventDefault();
}

function alignmentDragEnd() {
    if (!aligningBackground || !alignmentDragFrom) { return; }
    alignmentDragFrom = null;
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
function mapTool(e, tileName) {
    try {
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

function addUnit() {
    try {
        var unit = {};
        unit.charName = document.getElementById("unitName").value;
        unit.token = document.getElementById("unitToken").value;
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
    socket.emit('load_encounter', {clearLocations: document.getElementById("clearLocations").checked, encounterName: document.getElementsByClassName("selectedEncounter")[0].id, room: room, gmKey: gmKey});
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
function hideBottomDiv() {/*
    document.getElementById("mapContainer").style.height = "";
    document.getElementById("bottomPopupButton").style.top = "";
    document.getElementById("bottomPopupButton").onclick = function() {showBottomDiv();};
    document.getElementById("bottomPopupButton").children[0].src = "http://jp-bennett.com:17634/static/images/up.svg";
    document.getElementById("bottomDiv").style.display="none";*/
}

function showBottomDiv() {
/*    document.getElementById("mapContainer").style.height = "80%";
    document.getElementById("bottomPopupButton").style.top = "calc(80% - 40px)";
    document.getElementById("bottomPopupButton").onclick = function() {hideBottomDiv();};
    document.getElementById("bottomPopupButton").children[0].src = "http://jp-bennett.com:17634/static/images/down.svg";
    document.getElementById("bottomDiv").style.display="block";*/
}