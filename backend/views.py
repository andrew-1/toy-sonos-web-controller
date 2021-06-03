"""Code to serve html to client and communicate with client
through websockets
""" 

from __future__ import annotations
import asyncio
import json
from string import Template
from typing import TYPE_CHECKING


import aiohttp
from aiohttp import web


if TYPE_CHECKING:
    from sonos import SonosController


def _get_sonos_controller(app, path: str) -> SonosController:
    paths = app['controller_paths']
    controller_name = paths.get(path.lower(), "Living Room")
    return app['controllers'][controller_name]


def _html_response(name: str) -> web.Response:

    with open("../frontend/build/index.html", "r") as f:
       template = Template(f.read())
    return web.Response(text=template.substitute(TITLE=name), content_type='text/html')


async def _send_message(websocket: web.WebSocketResponse, message: dict):
    try:
        await websocket.send_json(message)
    except ConnectionResetError:
        pass


def send_queue(
    websockets: set[web.WebSocketResponse], 
    controller: SonosController, 
):
    queue = controller.get_queue()
    current_track, state = controller.current_track, controller.current_state
    for websocket in websockets.copy():
        asyncio.create_task(
            _send_message(
                websocket,
                {
                    "action": "update",
                    "data": [q_item._asdict() for q_item in queue],
                    "current_track": current_track,
                    "state": state,
                }
            )
        )


async def parse_client_command(
    message: str,
    controller: SonosController,
    websockets: set[web.WebSocketResponse],
):
    message = json.loads(message)
    
    command = message.get("command", None)
    if command is None:
        return
    elif command == "get_queue":
        send_queue(websockets, controller)
    else:
        controller.play_command(message["command"], message["args"])


async def index(request):
    controller = _get_sonos_controller(request.app, request.path)
    controller.load_playlist(request.query_string)

    websocket = web.WebSocketResponse()
    if not websocket.can_prepare(request).ok:
        return _html_response(controller.name)

    await websocket.prepare(request)
    websockets = controller.websockets
    websockets.add(websocket)

    send_queue(websockets, controller)
    
    async for msg in websocket:
        print(msg)
        if msg.type != aiohttp.WSMsgType.text:
            break
        await parse_client_command(msg.data, controller, websockets)

    websockets.remove(websocket)

    return websocket