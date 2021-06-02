"""Wrap for SoCo library features required for project"""

from __future__ import annotations
from collections import namedtuple
from dataclasses import dataclass, asdict
from typing import TYPE_CHECKING
import os
import string


if TYPE_CHECKING:
    from aiohttp import web
    from soco.core import SoCo
    from art_downloader import ArtDownloader
    from events import SonosEventHandler
    from typing import Callable


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

    def __init__(
        self, 
        device: SoCo, 
        art_downloader: ArtDownloader, 
        event_handler: SonosEventHandler,
        queue_sender: Callable[[set[web.WebSocketResponse], SonosController], None]
    ) -> None:
        
        self.device: SoCo = device

        self.websockets: set[web.WebSocketResponse] = set()
        self._art_downloader: ArtDownloader = art_downloader
        event_handler.controller_callback = self.sonos_event_callback
        self._event_handler: SonosEventHandler = event_handler

        self._queue: list[QueueItem] = []
        self._queue_update_required: bool = True
        self._current_state: str = ""
        self._current_track: int = 0
        self._queue_sender = queue_sender

    def sonos_event_callback(
        self, 
        queue_update_required: bool, 
        current_state: str, 
        current_track: int,
    ) -> None:

        self._queue_update_required = queue_update_required
        self.current_state = current_state
        self.current_track = current_track
        self._queue_sender(self.websockets, self)

    def art_download_callback(self, server_uri: str):
        for queue_item in self._queue:
            if queue_item.server_art_uri == server_uri:
                queue_item.art_available = True

        self._queue_sender(self.websockets, self)

    @staticmethod
    def _server_art_uri(artist: str, album: str):
        ascii_lower_case = set(c for c in string.ascii_letters)
        a_z_only = lambda s: "".join(c for c in s if c in ascii_lower_case)
        path = f"cache/{a_z_only(artist)}___{a_z_only(album)}.png"
        available = os.path.isfile(path)
        return path, available

    def _get_device_queue(self):
        """this is an expensive call, only want to make it if i think something has changed.."""
        return self.device.get_queue(
            full_album_art_uri=True, 
            max_items=9999999
        )

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

    def get_queue(self) -> list[QueueItem]:
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
