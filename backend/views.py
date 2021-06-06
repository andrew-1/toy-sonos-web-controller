"""Code to serve html to client and communicate with client
through websockets
""" 

from __future__ import annotations
from string import Template
from typing import TYPE_CHECKING


import aiohttp
from aiohttp import web


if TYPE_CHECKING:
    from controller import Controller


def _html_response(name: str) -> web.Response:
    with open("../frontend/build/index.html", "r") as f:
       template = Template(f.read())
    return web.Response(
        text=template.substitute(TITLE=name),
        content_type='text/html'
    )


async def index(request):
    controller: Controller = request.app['controllers'][request.path]
    controller.playback.load_playlist(request.query_string)

    websocket = web.WebSocketResponse()
    if not websocket.can_prepare(request).ok:
        return _html_response(controller.name)

    await websocket.prepare(request)
    
    controller.websockets.add(websocket)
    controller.websockets.send_queue(controller.queue_state.get_queue_dict())
    
    async for msg in websocket:
        print(msg)
        if msg.type != aiohttp.WSMsgType.text:
            break
        await controller.playback.parse_client_command(msg.data)

    controller.websockets.remove(websocket)

    return websocket