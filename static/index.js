'use strict'

let wsUri = (window.location.protocol=='https:'&&'wss://'||'ws://')+window.location.host+window.location.pathname;
let ws = new WebSocket(wsUri);
let current_index = null;

function loadImage(json) {
    let imgs = document.querySelectorAll(".art");
    for (let img of imgs) {
        if (img.dataset.arturi == json.src) {
            img.src = json.src
        };
    }
}

function sendCommand(command, args=[]) {
    let message = {
        command: command,
        args: args,
    }
    return ws.send(JSON.stringify(message))
}

function playIndex(index) {
    sendCommand("play_index", [index])
    updateDisplayedPlayingTrack(index)
}

function updateIncrement(increment) {
    if (!(current_index == null)) {
        updateDisplayedPlayingTrack(current_index + increment)
    }
}

function playNext() {
    sendCommand('play_next')
    updateIncrement(1)
}

function playPrevious() {
    sendCommand('play_previous')
    updateIncrement(-1)
}

function updateDisplayedPlayingTrack(index) {
    let div
    if (!(current_index == null)) {
        if (current_index == index) return;

        div = document.getElementById(current_index);
        div.style.backgroundColor = "";
    }
    
    div = document.getElementById(index);
    div.scrollIntoView({behavior: "smooth", block: "nearest", inline: "nearest"});
    div.style="background-color:rgb(240,240,240);";
    current_index = index;
}

function updatePlayPauseIcon(state) {
    let icon = document.getElementById("play_pause_icon")
    if (state == "PLAYING") {
        icon.innerHTML = "pause"
        icon.onclick = () => sendCommand("pause");
    } else if (state == "PAUSED_PLAYBACK") {
        icon.innerHTML = "play_arrow";
        icon.onclick = () => sendCommand("play");;
    }
}

function updatePlayingTrack(json) {
    if (json.state == "PLAYING" || json.state == "PAUSED_PLAYBACK") {
        updatePlayPauseIcon(json.state);
    }
    if ((json.state == "PLAYING" || json.state == "TRANSITIONING")) {
        updateDisplayedPlayingTrack(json.track);
    }
}

ws.onmessage = function (event) {
    let json = JSON.parse(event.data);

    if (json.action == "load_image") {
        loadImage(json);
    } else if (json.action == "current_track") {
        updatePlayingTrack(json);
    } else if (json.action == "reload") {
        location.reload();
    }
};
