import asyncio
from collections import defaultdict
import logging
from aiohttp.web_ws import WebSocketReady

import jinja2
import aiohttp_jinja2
from aiohttp import web, ClientSession
import soco
from soco import events_asyncio

from views import index
import sonos

soco.config.EVENTS_MODULE = events_asyncio


async def init_app():
    
    app = web.Application()
    app['websockets'] = defaultdict(set) 
    app['controllers'] = sonos.create_sonos_controllers()
    app['subscriptions'] = await sonos.setup_subscriptions(
        [controller.device for controller in app['controllers'].values()],
        app['websockets']
    )
    app['client_session'] = ClientSession()
    app.on_shutdown.append(shutdown)
    
    app.router.add_get('/', index)
    app.add_routes([web.static('/static', './static')])

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
    # logging.basicConfig(level=logging.INFO)

    app = init_app()
    web.run_app(app)


if __name__ == '__main__':
    main()