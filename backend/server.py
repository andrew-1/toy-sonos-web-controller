import asyncio
import os
import re
from typing import TYPE_CHECKING

from aiohttp import web, ClientSession
import soco

import views
from sonos import SonosController
from events import SonosEventHandler
from art_downloader import ArtDownloader


if TYPE_CHECKING:
    from soco.events_asyncio import Subscription


async def create_sonos_controllers() -> dict[str, SonosController]:
    """Creates sonos controllers
    The controller is the client and the event handler and art_downloader
    are the services
    """

    controllers = {}
    for device in soco.discovery.discover():
        subscription: Subscription = await device.avTransport.subscribe()
        event_handler = SonosEventHandler(subscription)

        client_session = ClientSession()
        queue = asyncio.Queue()
        art_downloader = ArtDownloader(client_session, queue)
        asyncio.create_task(art_downloader.run_queue())

        controllers[device.player_name] = SonosController(
            device, art_downloader, event_handler
        )

    return controllers


async def shutdown_sonos_controller(controllers: list[SonosController]):
    for controller in controllers.values():
        await controller._art_downloader.client_session.close()
        await controller._event_handler.subscription.unsubscribe()
        for websocket in controller.websockets.copy():
            asyncio.create_task(websocket.close())


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

    app['controllers'] = await create_sonos_controllers()

    app['controller_paths'] = _get_valid_paths(app['controllers'].keys())
    for path in app['controller_paths']:
        app.router.add_get(path, views.index)
    
    _create_art_cache_folder()
    app.add_routes([
        web.static('/cache', './cache'),
        web.static('/static', '../frontend/build/static'),
    ])

    app.on_shutdown.append(shutdown)

    return app


async def shutdown(app):
    await shutdown_sonos_controller(app['controllers'])


def main():
    app = init_app()
    web.run_app(app)


if __name__ == '__main__':
    main()