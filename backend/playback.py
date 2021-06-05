from __future__ import annotations
from functools import partial
import json
from typing import Callable, TYPE_CHECKING


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


