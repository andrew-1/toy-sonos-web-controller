import asyncio
import os
import typing
from typing import List

from aiohttp import ClientSession, web

import views

if typing.TYPE_CHECKING:
    from backend.sonos import AlbumArtDownload, SonosController

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
            print("downloading: ",album.sonos_uri)
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


