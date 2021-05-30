"""Clases to wrap soco libray features required for project"""

import asyncio
from collections import defaultdict, namedtuple
from dataclasses import dataclass, asdict
import typing
from typing import List, Dict
from types import SimpleNamespace
import os
import string

import soco
from soco.core import SoCo

import art_downloader


if typing.TYPE_CHECKING:
    from aiohttp import ClientSession

@dataclass
class QueueItem:
    """Container for an item in the queue"""
    title: str
    album: str
    artist: str
    sonos_art_uri: str
    position: int
    server_art_uri: str
    art_available: bool

    def _asdict(self):
        return asdict(self)


AlbumArtDownload = namedtuple("Album", "server_uri, sonos_uri")


class SonosController:
    """Wrapper for soco library functionality"""

    def __init__(self, device, art_downloader) -> None:
        self.device: SoCo = device
        self.name: str = device.player_name
        self._events: List[Dict, Dict] = [{}, defaultdict(str), defaultdict(str)]
        self._queue_update_required: bool = True
        self._queue: List[QueueItem] = []
        self._current_state: str = ""
        self._current_track: int = 0

        self._art_downloader = art_downloader

    def _feed_art_downloader(self) -> None:
        """returns an iterable of namedtuples with album art uris"""
        # a dictionary is used here to remove duplicates and preserve 
        # insertion order
        art_to_download = {
            AlbumArtDownload(
                item.server_art_uri, item.sonos_art_uri
            ): None
            for item in self._queue
            if not item.art_available
        }
        self._art_downloader.put_art_in_queue(art_to_download, self)

    def _get_device_queue(self):
        """this is an expensive call, only want to make it if i think something has changed.."""
        return self.device.get_queue(
            full_album_art_uri=True, 
            max_items=9999999
        )
    
    def _process_changes_in_event(self, event_variables):
        """Attempts to work out whether queue has changed"""
        # do this on strings, as hashable objects seem to be being created
        # on each call
        variables = {
            k: v 
            for k, v in event_variables.items() 
            if isinstance(v, str)
        }
        events = self._events
        events[:] = events[-2], events[-1], variables
        
        ns = SimpleNamespace()
        ns.different_number_of_tracks = lambda: (
            events[-2]['number_of_tracks'] != events[-1]['number_of_tracks']
        )
        ns.is_stopped = lambda: (
            events[-1]['transport_state'] == "STOPPED"
        )
        is_not_transitioning = lambda: (
            events[-1]['transport_state'] != "TRANSITIONING"
        )
        no_change_in_variables = lambda: (
            not set(events[-1].items()) - set(events[-2].items())
        )
        two_back_state_not_transitioning = lambda: (
            events[-3]['transport_state'] != "TRANSITIONING"
        )
        ns.not_two_identical_events_after_a_transition = lambda: (
            is_not_transitioning() 
            and no_change_in_variables()
            and two_back_state_not_transitioning()
        )

        # print(is_not_transitioning())
        # print(no_change_in_variables())
        # print(set(events[-1].items()) - set(events[-2].items()))
        # for event in events:
        #     print(event["transport_state"])
        return ns

    def process_event(self, event_variables):
        """Work out whether queue has changed
        """
        ns = self._process_changes_in_event(event_variables)

        self._queue_update_required = (
            ns.different_number_of_tracks()
            or ns.is_stopped()
            or ns.not_two_identical_events_after_a_transition()
        )
        
        self.current_state = event_variables['transport_state']
        self.current_track = int(event_variables['current_track']) - 1
        # print("Update required: ", self._queue_update_required)

    @staticmethod
    def _server_art_uri(artist: str, album: str):
        ascii_lower_case = set(c for c in string.ascii_letters)
        a_z_only = lambda s: "".join(c for c in s if c in ascii_lower_case)
        path = f"cache/{a_z_only(artist)}___{a_z_only(album)}.png"
        available = os.path.isfile(path)
        return path, available

    def get_queue(self) -> List[QueueItem]:
        if not self._queue_update_required:
            return self._queue
        self._queue_update_required = False
        get = lambda song, attr: getattr(song, attr, "Unknown")
        self._queue[:] = [
            QueueItem(
                get(song, "title"), 
                get(song, "album"), 
                get(song, "creator"), 
                get(song, "album_art_uri"), 
                i,
                *self._server_art_uri(
                    get(song, "creator"), 
                    get(song, "album")
                )
            )
            for i, song in enumerate(self._get_device_queue())
        ]
        self._feed_art_downloader()
        return self._queue
    
    def update_art_availablity(self, server_uri):
        for queue_item in self._queue:
            if queue_item.server_art_uri == server_uri:
                queue_item.art_available = True

    def load_playlist(self, name):
        for p in self.device.get_sonos_playlists():
            if p.title.lower() == name:
                self.device.clear_queue()
                self.device.add_to_queue(p)
                return

    def play_command(self, action, args):
        commands = {
            "play_index": self.device.play_from_queue,
            "play_previous": self.device.previous,
            "play_next": self.device.next,
            "play": self.device.play,
            "pause": self.device.pause,
        }
        do_nothing = lambda: None
        command = commands.get(action, do_nothing)
        command(*args)


def create_sonos_controllers(websockets: Dict[str, set]) -> Dict[str, SonosController]:

    controllers = {}
    for device in soco.discovery.discover():

        downloader = art_downloader.ArtDownloader(
            websockets[device.player_name]
        )
        asyncio.create_task(downloader.run_queue())
        controllers[device.player_name] = SonosController(device, downloader)

    return controllers
