from __future__ import annotations
import asyncio
import re
from typing import Awaitable, Callable, NamedTuple, TYPE_CHECKING

from aiohttp import ClientSession
import soco

from sonos import SonosQueueState
from events import SocoEventHandler
from art_downloader import ArtDownloader
from playback import PlaybackController, playback_controller_queues_empty
from queued_executors import QueuedAsyncExecutor, LastInQueuedThreadExecutor


if TYPE_CHECKING:
    from soco.events_asyncio import Subscription
    from soco.core import SoCo


def init_art_downloader() -> ArtDownloader:
    client_session = ClientSession()
    queue: QueuedAsyncExecutor = QueuedAsyncExecutor()
    return ArtDownloader(client_session, queue)


def init_playback_controller(
    device: SoCo
) -> tuple[PlaybackController, Callable[[], bool]]:

    play_pause_queue = LastInQueuedThreadExecutor()
    play_index_queue = LastInQueuedThreadExecutor()
    return (
        PlaybackController(
            device, play_pause_queue, play_index_queue
        ),
        playback_controller_queues_empty(
            play_pause_queue, play_index_queue
        ),
    )


async def init_event_handler(
    device: SoCo,
    controller: SonosQueueState, 
    playback_command_queue_empty: Callable[[], bool]
) -> SocoEventHandler:

    subscription: Subscription = await device.avTransport.subscribe()
    return SocoEventHandler(
        subscription, 
        controller.callback_sonos_event, 
        playback_command_queue_empty
    )


class Controller(NamedTuple):
    name: str
    queue_state: SonosQueueState
    playback: PlaybackController
    websockets: WebSockets


class Controllers(dict):
    """Provides access to speaker controller by valid url path"""
    def __init__(
        self,
        controllers: dict[str, Controller],
        clean_ups: list[Callable[[], Awaitable[None]]]
    ) -> None:

        self.update(controllers)
        self._clean_ups = clean_ups
        self._add_valid_paths_to_self()
        self.paths = {p for p in self.keys() if p.startswith("/")}

    async def clean_up(self):
        for clean_up in self._clean_ups:
            await clean_up()

    def _add_valid_paths_to_self(self) -> None:
        """Converts speaker names to lower case with no punctuation
        This is used to make it easy to provide the speaker name
        in the browser
        """
        alpha_numeric_path = lambda s: "/" + re.sub(r'\W+', '', s)
        alpha_numeric_path_lower = lambda s: alpha_numeric_path(s).lower()
        additional_paths = {
            a_n_p(name): controller
            for name, controller in self.items()
            for a_n_p in (alpha_numeric_path, alpha_numeric_path_lower)
        }
        self.update(additional_paths)


async def init_controllers(WebSockets) -> Controllers:
    """inits the object model"""

    controllers: dict[str, Controller] = {}
    clean_ups: list[Callable[[], Awaitable[None]]] = []

    device: SoCo
    for device in soco.discovery.discover():

        art_downloader = init_art_downloader()

        playback_controller, playback_command_queue_empty = \
            init_playback_controller(device)

        websockets = WebSockets()

        controller = SonosQueueState(
            playback_controller.get_queue, 
            art_downloader.enqueue_art, 
            websockets.send_queue,
        )

        event_handler = await init_event_handler(
            device, controller, playback_command_queue_empty
        )

        controllers[device.player_name] = Controller(
            device.player_name, controller, playback_controller, websockets
        )

        clean_ups.append(websockets.clean_up)
        clean_ups.append(event_handler.clean_up)
        clean_ups.append(art_downloader.clean_up)

    clean_ups.append(SocoEventHandler.shutdown_event_listener)

    return Controllers(controllers, clean_ups)
