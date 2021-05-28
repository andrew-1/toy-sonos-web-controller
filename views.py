"""Code to serve html to client and communicate with client
through websockets
""" 

import asyncio
from collections import namedtuple
import json
import os
import typing
from typing import List, Dict

import aiohttp_jinja2
import aiohttp
from aiohttp import web


if typing.TYPE_CHECKING:
    from sonos import SonosController, QueueItem
    from aiohttp import ClientSession


AlbumArt = namedtuple("Album", "server_uri, sonos_uri")


async def _download_art_to_server(album: AlbumArt, session) -> bool:
    if os.path.isfile(album.server_uri):
        return False

    try:
        async with session.get(album.sonos_uri) as response:
            with open(album.server_uri, "wb") as f:
                f.write(await response.content.read())
    except ValueError:
        # if something goes wrong whilst trying to download the art
        # delete the file
        os.remove(album.server_uri)
        return False

    return True


async def _get_albums(queue: List['QueueItem']) -> Dict[AlbumArt, None]:
    # a dictionary is used here to preserve insertion order
    return {
        AlbumArt(item.server_art_uri, item.sonos_art_uri): None
        for item in queue
    }


async def _download_art_and_send_update(
    queue: List['QueueItem'], 
    websockets: List[web.WebSocketResponse],
    session: 'ClientSession' 
) -> None:

    albums = await _get_albums(queue)
    for album in albums:
        if not await _download_art_to_server(album, session):
            continue

        for websocket in websockets.copy():
            try:
                await websocket.send_json(
                    {
                        'action': 'load_image', 
                        'src': album.server_uri,
                    }
                )
            except ConnectionResetError:
                pass


async def _download_art(queue, websockets, client_session):
    # art downloads quite slowly so this downloads the art then
    # sends a message all active sessions to reload art when available
    asyncio.create_task(
        _download_art_and_send_update(queue, websockets, client_session)
    )


def _get_sonos_controller(app, path: str) -> 'SonosController':
    paths = app['controller_paths']
    controller_name = paths.get(path.lower(), "Living Room")
    return app['controllers'][controller_name]


async def _send_current_state(
    websocket: web.WebSocketResponse, 
    current_track: int, 
    state: str
):
    try:
        await websocket.send_json(
            {
                'action': 'current_track',
                'track': current_track,
                'state': state,
            }
        )
    except ConnectionResetError:
        pass


async def _send_reload_message(websocket: web.WebSocketResponse):
    try:
        await websocket.send_json({'action': 'reload'})
    except ConnectionResetError:
        pass


def _request_page_reload(websockets):
    for websocket in websockets.copy():
        asyncio.create_task(
            _send_reload_message(websocket)
        )


def callback(
    websockets: List[web.WebSocketResponse], 
    controller: 'SonosController', 
    event
):
    """Callback function used by soco asyncio library to register
    a change of state on the device
    """
    # event is basically igored, it's just being used as a trigger to 
    # tell the code something changed
    if controller.has_queue_changed():
        _request_page_reload(websockets)
        return

    # might be wise to work out whether the state has changed in a 
    # relevant way rather than just sending it out over and over again
    for websocket in websockets.copy():
        asyncio.create_task(
            _send_current_state(
                websocket, 
                *controller.get_current_state(),
            )
        )


def render_html(request, queue):
    return aiohttp_jinja2.render_template(
        'index.html', request, {"queue": queue}
    )


async def parse_client_command(message: str, controller: 'SonosController'):
    message = json.loads(message)
    
    commands = {
        "play_index": controller.play_from_queue,
        "play_previous": controller.play_previous,
        "play_next": controller.play_next,
        "play": controller.play,
        "pause": controller.pause,
    }
    do_nothing = lambda: None
    command = commands.get(message["command"], do_nothing)
    command(*message["args"])


async def index(request):

    controller = _get_sonos_controller(request.app, request.path)
    controller.load_playlist(request.query_string)

    queue = controller.get_queue()

    websocket = web.WebSocketResponse()
    if not websocket.can_prepare(request).ok:
        return render_html(request, queue)

    await websocket.prepare(request)
    websockets = request.app['websockets'][controller.name]
    websockets.add(websocket)

    await _download_art(queue, websockets, request.app['client_session'])
    await _send_current_state(websocket, *controller.get_current_state())

    async for msg in websocket:
        if msg.type != aiohttp.WSMsgType.text:
            break
        await parse_client_command(msg.data, controller)

    websockets.remove(websocket)

    return websocket