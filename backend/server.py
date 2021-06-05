from __future__ import annotations
import os
import re
from typing import Awaitable, Callable, TYPE_CHECKING

from aiohttp import web, ClientSession
import soco

import views
from sonos import SonosController
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
    controller: SonosController, 
    playback_command_queue_empty: Callable[[], bool]
) -> SocoEventHandler:

    subscription: Subscription = await device.avTransport.subscribe()
    return SocoEventHandler(
        subscription, 
        controller.callback_sonos_event, 
        playback_command_queue_empty
    )


async def init_object_model() -> tuple[
    dict[str, SonosController], 
    dict[str, PlaybackController], 
    list[Callable[[], Awaitable[None]]]
]:
    """inits the object model"""

    controllers: dict[str, SonosController] = {}
    playback_controllers: dict[str, PlaybackController] = {}
    clean_ups: list[Callable[[], Awaitable[None]]] = []

    for device in soco.discovery.discover():

        art_downloader = init_art_downloader()

        playback_controller, playback_command_queue_empty = \
            init_playback_controller(device)

        controller = SonosController(
            device, art_downloader.enqueue_art, views.send_queue
        )

        event_handler = await init_event_handler(
            device, controller, playback_command_queue_empty
        )

        controllers[device.player_name] = controller
        playback_controllers[device.player_name] = playback_controller

        clean_ups.append(controller.clean_up)
        clean_ups.append(event_handler.clean_up)
        clean_ups.append(art_downloader.clean_up)

    clean_ups.append(SocoEventHandler.shutdown_event_listener)

    return controllers, playback_controllers, clean_ups


async def cleanup_object_model(
    clean_ups: list[Callable[[], Awaitable[None]]]
) -> None:

    for clean_up in clean_ups:
        await clean_up()


def _get_valid_paths(controller_names):
    """Converts speaker names to lower case with no punctuation
    This is used to make it easy to provide the speaker name
    in the browser
    """
    alpha_numeric_path = lambda s: "/" + re.sub(r'\W+', '', s)
    alpha_numeric_path_lower = lambda s: alpha_numeric_path(s).lower()
    return {
        a_n_p(name): name
        for name in controller_names
        for a_n_p in (alpha_numeric_path, alpha_numeric_path_lower)
    }


def _create_art_cache_folder():
    """Create a folder to store the art if it doens't already exist"""
    if not os.path.isdir("cache"):
        os.mkdir("cache")


async def init_app():
    """Initialise sonos controller web app"""
    app = web.Application()

    app['controllers'], app['playback_controllers'], app['clean_ups'] = \
        await init_object_model()

    app['controller_paths'] = _get_valid_paths(app['controllers'].keys())
    for path in app['controller_paths']:
        app.router.add_get(path, views.index)
    
    _create_art_cache_folder()

    app.add_routes([
        web.static('/cache', './cache'),
        web.static('/static', '../frontend/build/static'),
        web.static('/', '../frontend/build/'),
    ])

    app.on_shutdown.append(shutdown)

    return app


async def shutdown(app):
    await cleanup_object_model(app['clean_ups'])


def main():
    app = init_app()
    web.run_app(app)


if __name__ == '__main__':
    main()