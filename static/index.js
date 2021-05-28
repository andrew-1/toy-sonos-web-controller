'use strict'

let wsUri = (window.location.protocol=='https:'&&'wss://'||'ws://')+window.location.host+window.location.pathname;
let ws = new WebSocket(wsUri);
let current_index = null;

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

function loadImage(json) {
    let imgs = document.querySelectorAll(".art");
    for (let img of imgs) {
        if (img.dataset.arturi == json.src) {
            img.src = json.src
        };
    }
}

function updateDisplayedPlayingTrack(track) {
    let button
    if (!(current_index == null)) {
        button = document.getElementById(current_index);
        button.style.backgroundColor = "";
    }
    
    button = document.getElementById(track);
    button.scrollIntoView({behavior: "smooth", block: "nearest", inline: "nearest"});
    button.style="background-color:rgb(240,240,240);";
    current_index = track;
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