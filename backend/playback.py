from __future__ import annotations
from functools import partial
import json
import os
import string
from typing import Callable, TYPE_CHECKING

from sonos import QueueItem

if TYPE_CHECKING:
    from soco.core import SoCo
    from queued_executors import LastInQueuedThreadExecutor
    

class PlaybackController:
    """Play commands in soco block, if multiple skips are applied
    this can cause the server to lock up. This class is implemented
    to run the commands in a separate thread and if tasks queue up
    only the final item is processed 
    """

    def __init__(
        self, 
        device: SoCo,
        play_pause_queue: LastInQueuedThreadExecutor,
        play_index_queue: LastInQueuedThreadExecutor,
    ) -> None:

        self._device = device
        self.command_queue = {
            "play_index": (
                device.play_from_queue,
                play_index_queue,
            ),
            "play": (
                device.play,
                play_pause_queue
            ),
            "pause": (
                device.pause,
                play_pause_queue
            ),
        }

    def _play_command(self, action: str, args: tuple):
        if not action in self.command_queue:
            return
        command, queue = self.command_queue[action]
        queue.put_nowait(command, *args)
        
    async def parse_client_command(self, json_message: str):
        message: dict = json.loads(json_message)
        self._play_command(message["command"], message["args"])

    def playback_queues_empty(self):
        return (
            self._play_pause_queue.tasks_completed 
            and self._play_index_queue.tasks_completed
        )

    def load_playlist(self, name):
        for p in self._device.get_sonos_playlists():
            if p.title.lower() == name:
                self._device.clear_queue()
                self._device.add_to_queue(p)
                return

    def _get_device_queue(self):
        """This polls the sonos system to find out if the queue has 
        changed. It might be better to execute this in a seperate thread.
        """
        return self._device.get_queue(
            full_album_art_uri=True, 
            max_items=9999999
        )

    @staticmethod
    def _server_art_uri(artist: str, album: str):
        ascii_lower_case = set(c for c in string.ascii_letters)
        a_z_only = lambda s: "".join(c for c in s if c in ascii_lower_case)
        path = f"cache/{a_z_only(artist)}___{a_z_only(album)}.png"
        available = os.path.isfile(path)
        return path, available

    def get_queue(self):
        get = lambda song, attr: getattr(song, attr, "Unknown")
        return [
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


def _playback_controller_queues_empty(play_pause_queue, play_index_queue):
    return (
        play_pause_queue.tasks_completed 
        and play_index_queue.tasks_completed
    )

def playback_controller_queues_empty(
    play_pause_queue: LastInQueuedThreadExecutor,
    play_index_queue: LastInQueuedThreadExecutor,
) -> Callable[[], bool]:
    return partial(
        _playback_controller_queues_empty, 
        play_pause_queue, 
        play_index_queue
    )


