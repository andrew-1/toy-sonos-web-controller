import './App.css';
import React from 'react';
import loading from './loading.gif'


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
  console.log("state " + props.state)
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
class App extends React.Component {
  constructor(props) {
    super(props)
    
    console.log(this.getWebSocketURI())

  
    const websocket = new WebSocket(this.getWebSocketURI())
    this.state = {
      websocket: websocket,
      playlist: [],
      current_index: null,
      state: null,
    }
  };

  componentDidMount() {
    const websocket = this.state.websocket
    websocket.onmessage = (event) => {this.onMessage(event)}
    websocket.onopen = (event) => {this.onWebSocketOpen(event)}
  }

  onWebSocketOpen(event) {
    console.log("socket openened")
    this.sendCommand("get_queue")
  }

  onMessage(event) {
    let json = JSON.parse(event.data);
    console.log(json)
    this.setState({
      playlist: json.data,
      current_index: json.current_track,
      state: json.state === "TRANSITIONING" ? this.state.state: json.state
    })
};

  sendCommand(command, args=[]) {
    let message = {
        command: command,
        args: args,
    }
    return this.state.websocket.send(JSON.stringify(message))
  }  

  playNext() {
    console.log("playnext")
    this.setState(
      {current_index: this.state.current_index + 1}
    )
    this.sendCommand("play_next")

  }

  playPrevious() {
    this.setState(
      {current_index: this.state.current_index - 1}
    )
    this.sendCommand("play_previous")
  }

  playIndex(index) {
    this.setState({current_index: index});
    this.sendCommand("play_index", [index]);
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

  getWebSocketURI() {
    if (!process.env.NODE_ENV || process.env.NODE_ENV === 'development') {
      return "ws://localhost:8080/bedroom"
    }
    const protocol = ((window.location.protocol==='https:'&&'wss://')||'ws://')
    return protocol + window.location.host + window.location.pathname;
  }

  getServerPath() {
    if (!process.env.NODE_ENV || process.env.NODE_ENV === 'development') {
      return "http://localhost:8080/"
    }
    return ""
    console.log(window.location.protocol + window.location.host + "/")
    return window.location.protocol + window.location.host + "/";

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
          onClick = {(index) => this.playIndex(index)}
        />
      )
    });
    
    const footer = (
      <Footer 
        playPrevious = {() => this.playPrevious()} 
        playNext = {() => this.playNext()} 
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
