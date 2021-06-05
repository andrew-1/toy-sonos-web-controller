from __future__ import annotations
import asyncio
from abc import ABC, abstractmethod

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine
    from typing import Any


class QueuedExecutor(ABC):
    """Superclass to manage async/threaded queues"""
    def __init__(self) -> None:
        self._queue: asyncio.Queue = asyncio.Queue()
        self.tasks_completed: bool = True
        self._task = asyncio.create_task(self._run_queue())

    async def _run_queue(self):
        while True:
            func, args, kwargs = await self._queue.get()
            await self._run_command(func, *args, **kwargs)
            self.tasks_completed = self._queue.empty()
            self._queue.task_done()

    async def _graceful_exit(self):
        """place holder, not sure if i need this"""
        await self._queue.join()
        self._task.cancel()

    @abstractmethod
    def _run_command(self, func, *args, **kwargs):
        """This function should process the supplied func, args and 
        kwargs
        """
        pass

    @abstractmethod
    def put_nowait(self, func, *args, **kwargs):
        """Subclasses should declare the type signature for funcitons"""
        self.tasks_completed = False
        self._queue.put_nowait((func, args, kwargs))


class LastInQueuedThreadExecutor(QueuedExecutor):

    def __init__(self) -> None:
        self._loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()
        super().__init__()

    async def _run_command(self, func, *args, **kwargs):
        while self._queue.qsize() > 0:
            self._queue.task_done()
            func, args, kwargs = await self._queue.get()
        await self._loop.run_in_executor(None, func, *args, **kwargs)         

    def put_nowait(
        self, 
        func: Callable[..., None], 
        *args, 
        **kwargs
    ) -> None:
        """Puts a function with arguements into the queue"""
        super().put_nowait(func, *args, **kwargs)


class QueuedAsyncExecutor(QueuedExecutor):

    async def _run_command(self, func, *args, **kwargs):
        await func(*args, **kwargs)

    def put_nowait(
        self, 
        func: Callable[..., Coroutine[Any, Any, None]], 
        *args, 
        **kwargs
    ) -> None:
        """Puts a coroutine with arguements into the queue"""
        super().put_nowait(func, *args, **kwargs)


