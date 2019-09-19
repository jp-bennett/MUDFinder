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
            newMapText += `<div id="tile${x},${y}" onclick="mapClick(event, ${x}, ${y})"`;
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
            newMapText += `class='mapTile `;
            if (Data.mapArray[x][y].tile == "doorOpen") {
              if (Data.mapArray[x+1][y].tile =="floorTile" || Data.mapArray[x-1][y].tile =="floorTile") {
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
    //show the one that was passed
}

function populateEditChar (Data, unitNum) {
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
    if (document.getElementById("revealsMap")) {
        document.getElementById("revealsMap").checked = Data.unitList[playerUnitNum].revealsMap;
    }
}

