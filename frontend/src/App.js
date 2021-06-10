import './App.css';
import React from 'react';
import loading from './loading.gif'
import socketIOClient from "socket.io-client";


class Track extends React.Component {
  constructor(props) {
    super(props);
    this.boxRef = React.createRef();
  }

  componentDidMount () {
    if (this.props.current_track) {
      this.boxRef.current.scrollIntoView({behavior: "smooth"});
    }
  }

  render() {
    let props = this.props
    return (
    <div ref={this.boxRef}
      className="grid-container" 
      onClick={() => props.onClick(props.position)}
      style={
        props.current_track ? 
         {backgroundColor:'rgb(240,240,240)'}: 
         {backgroundColor:""}}
    >
      <img
          className="art"
          src={props.server_art_uri}
          onError= {(e) => {
            e.target.onerror = null; 
            e.target.src=loading
          }}
          data-arturi={props.image}
          alt=""
      >
      </img>
      <div className="title">{props.title}</div>
      <div className="album">{props.album}</div>
      <div className="artist">{props.artist}</div>
    </div>
    )
  }
}

function Footer(props) {
  return (
    <div className='footer'>
      <i className="material-icons" onClick={props.playPrevious}>skip_previous</i>
      <i className="material-icons" id="play_pause_icon" onClick={props.playPause}>
        {props.state === "PLAYING" ? "pause": "play_arrow"}
      </i>
      <i className="material-icons" onClick={props.playNext}>skip_next</i>
    </div>
  )
}

class WebSocketConnection {
  constructor(onMessage) {
    // this.onMessage = (event) => {onMessage(event)}
 
    console.log("Trying to open wedsocket")
    console.log(this.getURI())
    const websocket = new WebSocket(this.getURI());
    websocket.onmessage = (event) => {onMessage(event)};
    websocket.onopen = (event) => {console.log("socket opened")}
    websocket.onclose = (event) => {this.onWebSocketClose(event)};
    this.websocket = websocket

    // this.sendCommand = this.sendCommand.bind(this)
  }

  getURI() {
    if (!process.env.NODE_ENV || process.env.NODE_ENV === 'development') {
      return "ws://localhost:8080/bedroom"
    }
    const protocol = ((window.location.protocol==='https:'&&'wss://')||'ws://')
    return protocol + window.location.host + window.location.pathname;
  }
  
  onWebSocketClose(event) {
    console.log("socket closed")
    setTimeout(() => {this.openNewWebSocket()}, 5000);
  }

  sendCommand(message) {
    let send_message = (message) => {
      this.websocket.send(JSON.stringify(message))
    };
    send_message(message)
    // this.websocket.send(JSON.stringify(message));
  }  
}

class App extends React.Component {
  constructor(props) {
    super(props)
    this.onMessage = this.onMessage.bind(this);
    this.websocket = null;
    this.backend = "aiohttp";

    this.state = {
      playlist: [],
      current_index: null,
      state: null,
    }
  };

  componentDidMount() {
    this.websocket = new WebSocketConnection(this.onMessage);

    // if (this.state.backend === "aiohttp") {
    //   this.openNewWebSocket()
    // } else if (this.state.backend === "flask") {
    //   this.openNewSocketIO()
    // } 
  }

  openNewSocketIO() {
    console.log("Trying to open socketio")
    console.log(this.getSocketIOURI())
    const websocket = socketIOClient(this.getSocketIOURI());
    websocket.on("message", (event) => {this.onMessage(event)});
    websocket.on("connect", (event) => {console.log("socket opened")});

    websocket.on('disconnect', (event) => {this.onSocketIOClose(event)});
    this.setState({websocket: websocket});

  }
  onSocketIOClose(event) {
    console.log("socketio closed")
    setTimeout(() => {this.openNewSocketIO()}, 5000);
  }

  onMessage(event) {
    let json = JSON.parse(event.data);
    console.log(json);
    let new_state = {
      playlist: json.data,
      current_index: json.current_track,
      state: json.state === "TRANSITIONING" ? this.state.state: json.state
    }
    let update = (new_state) => {this.setState(new_state)}
    update(new_state)
  }

  sendCommand(command, args=[]) {
    let message = {
      command: command,
      args: args,
    }
    this.websocket.sendCommand(message)
  }  

  play(increment, index=this.state.current_index) {
    this.sendCommand("play_index", [index + increment])
    this.setState({current_index: index + increment})
  }

  playPause() {
    if (this.state.state === "PLAYING") {
      this.sendCommand("pause")
      this.setState({state: "PAUSED_PLAYBACK"})
    } else {
      this.sendCommand("play")
      this.setState({state: "PLAYING"})
    }
  }

  getSocketIOURI() {
    if (!process.env.NODE_ENV || process.env.NODE_ENV === 'development') {
      return "ws://localhost:8080/"
    }
    const protocol = ((window.location.protocol==='https:'&&'wss://')||'ws://')
    return protocol + window.location.host + "/";
  }


  getServerPath() {
    if (!process.env.NODE_ENV || process.env.NODE_ENV === 'development') {
      return "http://localhost:8080/"
    }
    return ""
  }

  render() {
    const tracks = this.state.playlist.map((track, idx) => {
      const key = (
        track.position.toString()
        + track.title
        + track.album 
        + track.art_available.toString() 
        + (track.position === this.state.current_index).toString()
      )
      return (
        <Track 
          key = {key}
          position = {track.position}
          title = {track.title}
          album = {track.album}
          artist = {track.artist}
          server_art_uri = {this.getServerPath() + track.server_art_uri}
          art_available = {track.art_available}
          current_track = {track.position === this.state.current_index}
          onClick = {(index) => this.play(0, index)}
        />
      )
    });
    
    const footer = (
      <Footer 
        playPrevious = {() => this.play(-1)} 
        playNext = {() => this.play(1)} 
        playPause = {() => this.playPause()}
        state = {this.state.state}
      />
    )
    return (
      <div>
      {tracks}
      {footer}
      </div>
    )
  }
}

export default App;
