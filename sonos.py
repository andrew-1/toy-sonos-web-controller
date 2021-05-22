import asyncio
from collections import defaultdict
import functools
import os
from typing import List, Dict, Set, DefaultDict
import string
from aiohttp import web

import soco
from soco import events_asyncio


class Song:
    def __init__(self, title, queue_position, track_number) -> None:
        self.title = title
        self.queue_position = queue_position
        self.track_number = track_number


class Album:
    def __init__(self, title: str, artist: str, art_uri: str, songs=None) -> None:
        self.title: str = title
        self.artist: str = artist
        self.art_uri: str = art_uri
        self.songs: List[str] = [] if songs is None else songs
    
    @property
    def back_ground_colour(self):
        if os.path.isfile(self.cached_art_file_name):
            with open(self.cached_art_file_name + ".background", "r") as f:
                return f"rgb{f.readline()}"
        return "black"

    @property
    def cached_art_file_name(self):
        ascii_lower_case = set(c for c in string.ascii_letters)
        a_z_only = lambda s: "".join(c for c in s if c in ascii_lower_case)
        return f"static/cache/{a_z_only(self.artist)}___{a_z_only(self.title)}.png"

    def __eq__(self, o: object) -> bool:
        return self.title == o.title and self.artist == o.artist

    def __hash__(self):
        return hash((self.title, self.artist))


class SonosController:
    """simple wrapper for soco library"""

    def __init__(self, device) -> None:
        self.device = device    
        self.name = device.player_name

    def _make_an_album(self, song):
        return Album(song.album, song.creator, song.album_art_uri)

    def albums(self) -> List[Album]:
        albums = []
        song_number = defaultdict(int)
        for q_position, sonos_song in enumerate(self.device.get_queue(full_album_art_uri=True)):
            album = self._make_an_album(sonos_song)
            if not albums or not albums[-1] == album:
                albums.append(album)
            else:
                album = albums[-1]

            song_number[album] += 1
            album.songs.append(
                Song(
                    sonos_song.title, 
                    q_position, 
                    song_number[album], 
                )
            )

        return albums

    def play_from_queue(self, index: int):
        self.device.play_from_queue(index)

    @property
    def playlist_position(self) -> int:
        return self.device.get_current_track_info()['playlist_position']


def create_sonos_controllers() -> Dict[str, SonosController]:
    return {
        device.player_name : SonosController(device)
        for device in soco.discovery.discover()
    }


async def _send_json(websocket: web.WebSocketResponse, event):
    try:
        await websocket.send_json(
            {
                'action': 'current_track',
                'track': int(event.variables['current_track']) - 1,
                'state': event.variables['transport_state'],
            }
        )
    except ConnectionResetError:
        pass

def callback(websockets, event):
    for websocket in list(websockets):
        asyncio.create_task(_send_json(websocket, event))


async def setup_subscriptions(
    devices: List[soco.SoCo], 
    websockets: DefaultDict[str, Set[web.WebSocketResponse]]
) -> Dict[str, events_asyncio.Subscription]:

    subscriptions = {}
    for device in devices:
        subscription = await device.avTransport.subscribe()
        subscription.callback = functools.partial(
            callback, websockets[device.player_name]
        )
        subscriptions[device.player_name] = subscription

    return subscriptions