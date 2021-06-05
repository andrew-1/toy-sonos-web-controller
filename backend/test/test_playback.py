
import asyncio
from time import sleep

import pytest

import queued_executors


@pytest.mark.asyncio
async def test_queue_thread_executor():
    """Check that the queue only runs the first in and last in
    the idea is that you execute the first command as soon
    as it's available then queue the other commands and only execute
    the last command in once the first one is executed
    """
    def sleep_and_append(length):
        sleep(length)
        outputs.append(length)
    outputs = []

    qte = queued_executors.LastInQueuedThreadExecutor()

    qte.put_nowait(sleep_and_append, 0.001)
    await asyncio.sleep(0.002)
    assert qte.tasks_completed == False
    qte.put_nowait(sleep_and_append, 0.0001)
    qte.put_nowait(sleep_and_append, 0.0002)
    qte.put_nowait(sleep_and_append, 0.002)

    await qte._queue.join()
    assert qte.tasks_completed == True

    qte._task.cancel()

    assert tuple(outputs) == (0.001, 0.002)


@pytest.mark.asyncio
async def test_queued_async_executor():
    """add tasks to the queue and check they ran"""
    async def append(length):
        outputs.append(length)
    outputs = []

    executor = queued_executors.QueuedAsyncExecutor()

    executor.put_nowait(append, 0.001)
    await asyncio.sleep(0.002)
    executor.put_nowait(append, 0.0001)
    executor.put_nowait(append, 0.0002)
    executor.put_nowait(append, 0.002)

    await executor._queue.join()
    executor._task.cancel()

    assert tuple(outputs) == (0.001, 0.0001, 0.0002, 0.002)

