"""Download art from using the very slow sonos album art uris"""

from __future__ import annotations
import os
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    import asyncio
    from backend.sonos import AlbumArtDownload, SonosController
    from aiohttp import ClientSession


class ArtDownloader:
    """Downloads art for speaker queues"""
    def __init__(
        self, 
        client_session: ClientSession, 
        queue: asyncio.Queue
    ) -> None:
        
        self.client_session = client_session
        self.queue = queue

    async def run_queue(self):
        while True:
            server_uri, download_art, controller = await self.queue.get()
            if not os.path.isfile(server_uri):
                await download_art()
                controller.art_download_callback(server_uri)
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
        album_art_downloads: list[AlbumArtDownload], 
        controller: SonosController
    ) -> None:
        for album in album_art_downloads:
            download_art = lambda album=album: (
                self._download_art_to_server(album)
            )
            self.queue.put_nowait((
                album.server_uri, download_art, controller
            ))


