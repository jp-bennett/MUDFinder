const chunk_size = 64 * 1024;
var loreImages = new Array();
function updateMap(Data) {
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
          if ((typeof Data.mapArray[x+1] !== "undefined" && Data.mapArray[x+1][y].tile =="floorTile") || (typeof Data.mapArray[x-1] !== "undefined" && Data.mapArray[x-1][y].tile =="floorTile")) {
            newMapText += "doorTileAOpen";
          } else {
            newMapText += "doorTileBOpen";
          }
        } else if (Data.mapArray[x][y].tile == "doorClosed") {
          if (Data.mapArray[x+1][y].tile =="floorTile" || Data.mapArray[x-1][y].tile =="floorTile") {
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
          } else if (Data.mapArray[x+1][y].tile =="floorTile" || Data.mapArray[x-1][y].tile =="floorTile") {
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
      if (typeof Data.unitList[i].x !== "undefined") {
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
        document.getElementById(`tile${Data.unitList[i].x},${Data.unitList[i].y}`).className += " selectableUnit"
        document.getElementById(`tile${Data.unitList[i].x},${Data.unitList[i].y}`).attributes.units.value += i + " ";
      }
    }
    if (Data.inInit /*&& Data.initiativeList[Data.initiativeCount].movePath.length > 0*/) {
      tmpHTML = ""
      for (i = 0; i<Data.initiativeList[Data.initiativeCount].movePath.length;i++) {
        moveLoc = Data.initiativeList[Data.initiativeCount].movePath[i];
        tmpHTML += `<div style="width:${zoomSize/10}px;height:${zoomSize/10}px;position:absolute;top:${moveLoc[0]*zoomSize+zoomSize/2.2}px;left:${moveLoc[1]*zoomSize+zoomSize/2.2}px;background:${Data.initiativeList[Data.initiativeCount].color};"></div>`;
      }
      document.getElementById("mapGraphic").innerHTML += tmpHTML
      document.getElementById("movement").innerText = Math.floor(Data.initiativeList[Data.initiativeCount].distance) * 5
    }
  }
}
function enableTab(tabName) {
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
}

function populateEditChar (Data, unitNum) {
    if (Data.unitList.length == 0) {return}
    for (x = 0; x < Data.unitList.length; x++){
        if (Data.unitList[x].unitNum == unitNum){
            playerUnitNum = x;
            break;
        }
    }
    document.getElementById("editCharNum").innerText = playerUnitNum;
    document.getElementById("charactername").innerText = Data.unitList[playerUnitNum].charName;
    document.getElementById("charShortName").value = Data.unitList[playerUnitNum].charShortName;
    document.getElementById("playerColor").value = Data.unitList[playerUnitNum].color;
    document.getElementById("customColor").value = Data.unitList[playerUnitNum].color;
    if (document.getElementById("playerColor").value == "") {
        document.getElementById("customColorDiv").style.display = "block";
        document.getElementById("playerColor").value = "custom";
    } else {
        document.getElementById("customColorDiv").style.display = "none";
    }
    document.getElementById("perception").value = Data.unitList[playerUnitNum].perception;
    document.getElementById("movementSpeed").value = Data.unitList[playerUnitNum].movementSpeed;
    document.getElementById("dex").value = Data.unitList[playerUnitNum].dex;
    document.getElementById("size").value = Data.unitList[playerUnitNum].size;
    document.getElementById("darkvision").checked = Data.unitList[playerUnitNum].darkvision;
    document.getElementById("lowLight").checked = Data.unitList[playerUnitNum].lowLight;
    document.getElementById("trapfinding").checked = Data.unitList[playerUnitNum].trapfinding;
    document.getElementById("hasted").checked = Data.unitList[playerUnitNum].hasted;
    document.getElementById("permanentAbilities").value = Data.unitList[playerUnitNum].permanentAbilities;
    if (isGM) {
        document.getElementById("init").value = Data.unitList[playerUnitNum].initiative;
        document.getElementById("revealsMap").checked = Data.unitList[playerUnitNum].revealsMap;
    }
}

function previewLoreFile () {
    document.getElementById("loreFilePreview").src = URL.createObjectURL(document.getElementById("loreFileUpload").files[0])
}



function uploadLore () { //https://github.com/miguelgrinberg/socketio-examples
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
}
function readFileChunk(file, offset, length, success, error) {
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
}

function onReadSuccess(file, offset, length, data) {
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
}

function updateLore(msg, num) {
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


}

function enableLoreTab(tabName) {
    console.log(tabName);
    //hide all of them
    children = document.getElementById("lorePage").children
    for (x = 0; x < children.length; x++) {
        children[x].style.display = "none";
    }
    document.getElementById(`loreTab${tabName}`).style.display = "block"

}
function changeLoreVisibility(i) {
    if (isGM) {
        socket.emit("lore_visible", room, gmKey, i);
    } else {
        socket.emit("lore_visible", room, charName, i);
    }
}

function deleteLore(i) {
    if (isGM) {
        socket.emit("delete_lore", room, gmKey, i);
    } else {
        socket.emit("delete_lore", room, charName, i);
    }
}

function sendLoreURL () {
    if (document.getElementById("loreFileUpload").value == "") {
        console.log(document.getElementById("loreURL").value)
        socket.emit("lore_url", room, document.getElementById("loreURL").value, document.getElementById("loreName").value, document.getElementById("loreText").value, charName);
    } else {
        uploadLore();
    }
}

function previewLoreURL (value) {
    document.getElementById("loreFilePreview").src = value;
}

function onReadError(file, offset, length, error) {
    console.log('Upload error for ' + file.name + ': ' + error);
    this.done = true;
}

function downloadLoreImage(slotNum) {
    socket.emit("get_lore_file", room, slotNum, function (returnedImage){
        loreImages[slotNum] = returnedImage;
        document.getElementById(`loreIMG${slotNum}`).src = "data:image;base64, " + loreImages[slotNum];
    })
}

function changeItemCat(target) {
    if (target.value == "Custom") {
        document.getElementById("itemSelect").style.display = "none"
        document.getElementById("itemText").style.display = "block"
    } else {
        document.getElementById("itemSelect").style.display = "block"
        document.getElementById("itemText").style.display = "none"
    }
}

