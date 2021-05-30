import asyncio
import os
import typing
from typing import List

from aiohttp import ClientSession, web

import views

if typing.TYPE_CHECKING:
    from sonos import AlbumArtDownload, SonosController

class ArtDownloader:
    def __init__(
        self, 
        websockets: List[web.WebSocketResponse]
    ) -> None:
        
        self.client_session = ClientSession()
        self.queue = asyncio.Queue()
        self.websockets = websockets

    async def run_queue(self):
        while True:
            server_uri, download_art, controller = await self.queue.get()
            if not os.path.isfile(server_uri):
                await download_art()
                controller.update_art_availablity(server_uri)
                views.send_queue(self.websockets, controller)
            self.queue.task_done()
    
    async def _download_art_to_server(self, album: 'AlbumArtDownload') -> None:
        try:
            async with self.client_session.get(album.sonos_uri) as response:
                with open(album.server_uri, "wb") as f:
                    async for data in response.content.iter_any():
                        f.write(data)
        except ValueError:
            # if something goes wrong whilst trying to download the art
            # delete the file
            os.remove(album.server_uri)

    def put_art_in_queue(
        self, 
        album_art_downloads: List['AlbumArtDownload'], 
        controller: 'SonosController'
    ) -> None:
        for album in album_art_downloads:
            download_art = lambda album=album: (
                self._download_art_to_server(album)
            )
            self.queue.put_nowait((
                album.server_uri, download_art, controller
            ))



# async def _download_art_to_server(
#     album: 'AlbumArtDownload', 
#     session: 'ClientSession', 
# ) -> None:

#     try:
#         async with session.get(album.sonos_uri) as response:
#             with open(album.server_uri, "wb") as f:
#                 async for data in response.content.iter_any():
#                     f.write(data)
#     except ValueError:
#         # if something goes wrong whilst trying to download the art
#         # delete the file
#         os.remove(album.server_uri)
    

# async def _download_art(
#     queue: List['QueueItem'], 
#     websockets: Set[web.WebSocketResponse], 
#     client_session: ClientSession, 
#     controller: 'SonosController', 
#     art_queue: asyncio.Queue
# ):
#     """Loops through all albums, creates coroutine to download art
#     creates sync functions to update the availablity of the art in the 
#     queue and to update the queue on the server
#     """
#     # art downloads quite slowly so this downloads the art then
#     # sends a message all active sessions to reload art when available
#     albums = await _get_album_art_not_downloaded(queue)
#     for album in albums:
#         download_art = lambda album=album: (
#             _download_art_to_server(album, client_session)
#         )

#         update_availability = lambda album=album: (
#             controller.update_art_availablity(album.server_uri)
#         )
#         update_queue = lambda: _send_queue(websockets, controller)

#         await art_queue.put((
#             album.server_uri, download_art, 
#             update_availability, update_queue
#         ))


# async def _download_art(
#     albums: List[AlbumArtDownload]
#     client_session: ClientSession, 
#     controller: 'SonosController', 
#     art_queue: asyncio.Queue
# ):
#     """Loops through all albums, creates coroutine to download art
#     creates sync functions to update the availablity of the art in the 
#     queue and to update the queue on the server
#     """
#     # art downloads quite slowly so this downloads the art then
#     # sends a message all active sessions to reload art when available
#     for album in albums:
#         download_art = lambda album=album: (
#             _download_art_to_server(album, client_session)
#         )

#         update_availability = lambda album=album: (
#             controller.update_art_availablity(album.server_uri)
#         )
#         update_queue = lambda: _send_queue(websockets, controller)

#         await art_queue.put((
#             album.server_uri, download_art, 
#             update_availability, update_queue
#         ))

