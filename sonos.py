"""Clases to wrap soco libray features required for project"""

from typing import List, Dict, Tuple, NamedTuple
import string

import soco
from soco.core import SoCo


class QueueItem(NamedTuple):
    """Container for an item in the queue"""
    title: str
    album: str
    artist: str
    sonos_art_uri: str
    position: int

    @property
    def server_art_uri(self):
        ascii_lower_case = set(c for c in string.ascii_letters)
        a_z_only = lambda s: "".join(c for c in s if c in ascii_lower_case)
        return f"static/cache/{a_z_only(self.artist)}___{a_z_only(self.album)}.png"


class SonosController:
    """Wrapper for soco library functionality"""

    def __init__(self, device) -> None:
        self.device: SoCo = device
        self.name: str = device.player_name
        self._queue_history = (None, None)

    def _get_device_queue(self):
        return self.device.get_queue(
            full_album_art_uri=True, 
            max_items=9999999
        )

    def get_queue(self) -> List[QueueItem]:
        queue = [
            QueueItem(
                song.title, song.album, song.creator, song.album_art_uri, i
            )
            for i, song in enumerate(self._get_device_queue())
        ]
        self._queue_history = self._queue_history[-1], queue
        return queue
    
    def load_playlist(self, name):
        for p in self.device.get_sonos_playlists():
            if p.title.lower() == name:
                self.device.clear_queue()
                self.device.add_to_queue(p)
                return

    def has_queue_changed(self) -> bool:
        _ = self.get_queue()
        return self._queue_history[0] != self._queue_history[1]

    def play_from_queue(self, index: int):
        self.device.play_from_queue(index)

    def play_next(self):
        self.device.next()

    def play_previous(self):
        self.device.previous()

    def play(self):
        self.device.play()

    def pause(self):
        self.device.pause()

    def get_current_state(self) -> Tuple[int, str]:
        return (
            int(self.device.get_current_track_info()["playlist_position"]) - 1,
            self.device.get_current_transport_info()["current_transport_state"],
        )


def create_sonos_controllers() -> Dict[str, SonosController]:
    return {
        device.player_name : SonosController(device)
        for device in soco.discovery.discover()
    }
