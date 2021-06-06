from __future__ import annotations
import asyncio
import os
from typing import TYPE_CHECKING

from aiohttp import web

from controller import init_controllers
import views


if TYPE_CHECKING:
    from controller import Controllers


class WebSockets(set):
    async def clean_up(self) -> None:
        for websocket in self.copy():
            asyncio.create_task(websocket.close())

    async def _send_message(self, websocket, message):
        try:
            await websocket.send_json(message)
        except ConnectionResetError:
            pass

    def send_queue(self, queue: dict):
        for websocket in self.copy():
            asyncio.create_task(
                self._send_message(websocket, queue)
            )


def _create_art_cache_folder():
    """Create a folder to store the art if it doens't already exist"""
    if not os.path.isdir("cache"):
        os.mkdir("cache")


async def init_app(controllers: Controllers):
    """Initialise sonos controller web app"""
    app = web.Application()
    app['controllers'] = controllers
    
    for path in controllers.paths:
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
    controllers: Controllers = app['controllers']
    await controllers.clean_up()


async def a_main():
    controllers: Controllers = await init_controllers(WebSockets)
    runner = web.AppRunner(await init_app(controllers))

    await runner.setup()
    site = web.TCPSite(runner)    
    await site.start()

    print("Server up")
    try:
        await asyncio.Event().wait()
    finally:
        await runner.cleanup()


if __name__ == '__main__':
    try:
        asyncio.run(a_main())
    except KeyboardInterrupt:
        pass
