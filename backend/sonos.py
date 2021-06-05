"""Wrap for SoCo library features required for project"""

from __future__ import annotations
import asyncio
from collections import namedtuple
from dataclasses import dataclass, asdict

from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from aiohttp import web
    from typing import Callable, Iterable


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


AlbumArtDownload = namedtuple("AlbumArtDownload", "server_uri, sonos_uri")


class SonosController:
    """Wrapper for soco library functionality"""

    def __init__(
        self, 
        get_device_queue: Callable[[], list[QueueItem]], 
        name: str,
        enqueue_art: Callable[[Iterable[AlbumArtDownload], Callable[[str], None]], None], 
        queue_sender: Callable[[set[web.WebSocketResponse], SonosController], None]
    ) -> None:
        
        self.name: str = name
        self._get_queue = get_device_queue
        self.websockets: set[web.WebSocketResponse] = set()

        self._queue: list[QueueItem] = []
        self._queue_update_required: bool = True
        self._current_state: str = ""
        self._current_track: int = 0

        self._enqueue_art = enqueue_art
        self._queue_sender = queue_sender

    async def clean_up(self) -> None:
        for websocket in self.websockets.copy():
            asyncio.create_task(websocket.close())

    def callback_sonos_event(
        self, 
        queue_update_required: bool, 
        current_state: str, 
        current_track: int,
    ) -> None:

        self._queue_update_required = queue_update_required
        self.current_state = current_state
        self.current_track = current_track
        self._queue_sender(self.websockets, self)

    def callback_art_downloaded(self, server_uri: str):
        for queue_item in self._queue:
            if queue_item.server_art_uri == server_uri:
                queue_item.art_available = True

        self._queue_sender(self.websockets, self)


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
        self._enqueue_art(art_to_download.keys(), self.callback_art_downloaded)

    def get_queue(self) -> list[QueueItem]:
        if not self._queue_update_required:
            return self._queue
        self._queue_update_required = False
        self._queue = self._get_queue()
        self._feed_art_downloader()
        return self._queue


