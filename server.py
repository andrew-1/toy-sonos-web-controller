import asyncio
from collections import defaultdict
import functools
import os
import re
from typing import List, DefaultDict, Dict, Set

import jinja2
import aiohttp_jinja2
from aiohttp import web, ClientSession
import soco
from soco import events_asyncio

import views
import sonos


soco.config.EVENTS_MODULE = events_asyncio


async def _create_art_cache_folder():
    if not os.path.isdir("static"):
        raise Exception("The script needs to be run from the root directory") 
    
    if not os.path.isdir("static/cache"):
        os.mkdir("static/cache")


async def _setup_subscriptions(
    controllers: List[sonos.SonosController], 
    websockets: DefaultDict[str, Set[web.WebSocketResponse]]
) -> Dict[str, events_asyncio.Subscription]:

    subscriptions = {}
    for controller in controllers:
        subscription = await controller.device.avTransport.subscribe()
        subscription.callback = functools.partial(
            views.callback, websockets[controller.device.player_name], controller
        )
        subscriptions[controller.device.player_name] = subscription

    return subscriptions


async def _get_valid_paths(controllers: List[sonos.SonosController]):
    alpha_numeric_path = lambda s: "/" + re.sub(r'\W+', '', s)
    alpha_numeric_path_lower = lambda s: alpha_numeric_path(s).lower()

    return {
        a_n_p(name): name
        for name in controllers
        for a_n_p in (alpha_numeric_path, alpha_numeric_path_lower)
    }


async def init_app():
    app = web.Application()
    
    app['websockets'] = defaultdict(set) 

    app['controllers'] = sonos.create_sonos_controllers()
    app['subscriptions'] = await _setup_subscriptions(
        app['controllers'].values(),
        app['websockets']
    )

    app['client_session'] = ClientSession()
    asyncio.create_task(_create_art_cache_folder())

    app['controller_paths'] = await _get_valid_paths(app['controllers'])
    for path in app['controller_paths']:
        app.router.add_get(path, views.index)
    app.add_routes([web.static('/static', './static')])

    app.on_shutdown.append(shutdown)

    aiohttp_jinja2.setup(
        app, loader=jinja2.FileSystemLoader('./templates')
    )
    return app


async def shutdown(app):
    await app['client_session'].close()

    for subscription in app["subscriptions"].values():
        await subscription.unsubscribe()
    await events_asyncio.event_listener.async_stop()

    wss = [ws for set_ in app['websockets'].values() for ws in set_]
    for ws in wss:
        asyncio.create_task(ws.close())


def main():
    app = init_app()
    web.run_app(app)


if __name__ == '__main__':
    main()