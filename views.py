import asyncio
from collections import Counter
import logging
import os

import aiohttp_jinja2
import aiohttp
from aiohttp import web
from PIL import Image

from sonos import SonosController

log = logging.getLogger(__name__)


def _get_background_image(file_name):

    with Image.open(file_name, "r") as im:
        im = im.resize((150, 150)).convert("RGB")
        pixels = list(
            tuple(v // 10 for v in rgb)
            for rgb in im.getdata()
        )
        return tuple(10 * v for v in Counter(pixels).most_common(1)[0][0])

async def _cache_art(album, session) -> bool:
    print(album.art_uri)
    if os.path.isfile(album.cached_art_file_name):
        return False

    async with session.get(album.art_uri) as response:
        with open(album.cached_art_file_name, "wb") as f:
            f.write(await response.content.read())

    rgb = _get_background_image(album.cached_art_file_name)
    with open(album.cached_art_file_name + ".background", "w") as f:
        f.write("({},{},{})".format(*rgb))

    return True


async def cache_art_and_send_update(albums, websockets, session):
    # want to do this in order, bandwidth for io on device seems
    # to be limited (based on my perception - not tested), 
    # so would prefer first images to load first

    # make copy incase it gets mutated whilst sending message
    
    for album in albums:
        if not await _cache_art(album, session):
            continue

        websockets_copy = list(websockets)
        print(websockets_copy)
        for websocket in websockets_copy:
            try:
                await websocket.send_json(
                    {
                        'action': 'load_image', 
                        'src': album.cached_art_file_name,
                        'background_colour': album.back_ground_colour,
                    }
                )
            except ConnectionResetError:
                # something happened to the websocket whilst iterating
                pass


async def index(request):
    ws_current = web.WebSocketResponse()
    ws_ready = ws_current.can_prepare(request)

    controller_name = "Living Room"
    # controller_name = "Bedroom"
    controller: SonosController = request.app['controllers'][controller_name]

    albums = controller.albums()

    if not ws_ready.ok:
        return aiohttp_jinja2.render_template(
            'index.html', 
            request, 
            {
                "albums":albums, 
                "playlist_position": int(controller.playlist_position) - 1
            }
        )

    await ws_current.prepare(request)
    
    # art downloads quite slowly so this downloads the art then
    # sends a message all active sessions to reload art when available
    asyncio.create_task(
        cache_art_and_send_update(
            albums, 
            request.app['websockets'][controller_name], 
            request.app['client_session'],
        )
    )
    request.app['websockets'][controller_name].add(ws_current)

    async for msg in ws_current:
        print(msg)
        if msg.type != aiohttp.WSMsgType.text:
            break
        
        controller.play_from_queue(int(msg.data))

    request.app['websockets'][controller_name].remove(ws_current)

    return ws_current