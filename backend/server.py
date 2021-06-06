from __future__ import annotations
import asyncio
import os
from typing import TYPE_CHECKING

from aiohttp import web

from controller import init_controllers
import views


if TYPE_CHECKING:
    from controller import Controllers


def _create_art_cache_folder():
    """Create a folder to store the art if it doens't already exist"""
    if not os.path.isdir("cache"):
        os.mkdir("cache")


async def init_app(): #controllers: Controllers):
    """Initialise sonos controller web app"""
    app = web.Application()
    controllers = app['controllers'] = await init_controllers()
    for path in controllers.keys():
        if not path.startswith("/"):
            continue
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


def main():
    # controllers = await init_controllers()
    app = init_app()
    web.run_app(app)

# async def main():
#     # add stuff to the loop, e.g. using asyncio.create_task()
#     # ...

#     runner = web.AppRunner(await init_app())
#     await runner.setup()
#     site = web.TCPSite(runner)    
#     await site.start()

#     # # add more stuff to the loop, if needed
#     # ...

#     # # wait forever
#     await asyncio.Event().wait()




if __name__ == '__main__':
    # asyncio.run(main())
    main()