import asyncio
from collections import Counter
import json
import os

import aiohttp_jinja2
import aiohttp
from aiohttp import web
from PIL import Image

from sonos import SonosController


def _get_background_image(file_name):

    with Image.open(file_name, "r") as im:
        im = im.resize((150, 150)).convert("RGB")
        pixels = list(
            tuple(v // 10 for v in rgb)
            for rgb in im.getdata()
        )
        return tuple(10 * v for v in Counter(pixels).most_common(1)[0][0])

async def _cache_art(album, session) -> bool:
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

        for websocket in websockets.copy():
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

async def download_art(albums, websockets, client_session):
    # art downloads quite slowly so this downloads the art then
    # sends a message all active sessions to reload art when available
    asyncio.create_task(
        cache_art_and_send_update(albums, websockets, client_session)
    )


def get_sonos_controller(app, path: str) -> SonosController:
    paths = app['controller_paths']
    controller_name = paths.get(path.lower(), "Living Room")
    return app['controllers'][controller_name]


def render_html(request, albums, controller):
    return aiohttp_jinja2.render_template(
        'index.html', 
        request, 
        {
            "albums": albums, 
            "playlist_position": int(controller.playlist_position) - 1
        }
    )


async def parse_command(message: str, controller: SonosController):
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

    controller = get_sonos_controller(request.app, request.path)
    albums = controller.albums()

    websocket = web.WebSocketResponse()
    if not websocket.can_prepare(request).ok:
        return render_html(request, albums, controller)

    await websocket.prepare(request)
    websockets = request.app['websockets'][controller.name]
    websockets.add(websocket)

    await download_art(albums, websockets, request.app['client_session'])
    await controller.send_current_state(websocket)
    async for msg in websocket:
        print(msg)
        if msg.type != aiohttp.WSMsgType.text:
            break
        await parse_command(msg.data, controller)

    websockets.remove(websocket)

    return websocket