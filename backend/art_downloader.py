"""Download art from using the very slow sonos album art uris"""

from __future__ import annotations
import os
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from backend.sonos import AlbumArtDownload
    from aiohttp import ClientSession
    from queued_executors import QueuedAsyncExecutor
    from typing import Callable, Iterable


class ArtDownloader:
    """Downloads art for speaker queues
    io on the sonos is quite slow so this is done concurrently using
    async
    """
    def __init__(
        self, 
        client_session: ClientSession,
        queue: QueuedAsyncExecutor,
    ) -> None:
        
        self.client_session = client_session
        self.queue = queue 

    async def clean_up(self) -> None:
        await self.client_session.close()
        
    async def _download_art_to_server(self, album: 'AlbumArtDownload') -> None:
        try:
            print("downloading: ",album.sonos_uri)
            async with self.client_session.get(album.sonos_uri) as response:
                with open(album.server_uri, "wb") as f:
                    async for data in response.content.iter_any():
                        f.write(data)
        except ValueError:
            os.remove(album.server_uri)
    
    async def command(self, album, callback_art_downloaded) -> None:
        if not os.path.isfile(album.server_uri):
            await self._download_art_to_server(album)
            callback_art_downloaded(album.server_uri)

    def enqueue_art(
        self, 
        album_art_downloads: Iterable[AlbumArtDownload], 
        callback_art_downloaded: Callable[[str], None]
    ) -> None:
        for album in album_art_downloads:
            self.queue.put_nowait(
                self.command, album, callback_art_downloaded
            )
        