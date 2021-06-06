from __future__ import annotations
import asyncio
from functools import partial
import json
import os
import sys
from threading import Thread
from typing import TYPE_CHECKING

from flask import Flask, send_from_directory
from flask_socketio import SocketIO, emit

from controller import init_controllers, Controllers


if TYPE_CHECKING:
    from controller import Controller


app = Flask(__name__, static_folder='../frontend/build', static_url_path='/')
socketio = SocketIO(app, cors_allowed_origins="*")


@app.route('/bedroom')
def bedroom():
    print("here", flush=True, file=sys.stdout)
    return app.send_static_file('index.html')


@app.route('/cache/<path:filename>')
def base_static(filename):
    path = os.path.join(app.root_path, "cache")
    return send_from_directory(path, filename)


@socketio.event
def message(data):
    print(data)
    controller: Controller = controllers["Bedroom"]
    asyncio.run_coroutine_threadsafe(
        controller.playback.parse_client_command(json.dumps(data)), 
        loop
    )


@socketio.event
def connect():
    print("sending queue")
    queue = controllers["Bedroom"].queue_state.get_queue_dict()
    emit("message", {"data": json.dumps(queue)})


async def outbound():
    
    queue = controllers["Bedroom"].queue_state.get_queue_dict()
    socketio.emit("message", {"data": json.dumps(queue)})


def start_background_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()


loop = asyncio.new_event_loop()
t = Thread(target=start_background_loop, args=(loop,), daemon=True)
t.start()

task = asyncio.run_coroutine_threadsafe(init_controllers(), loop)
controllers: Controllers = task.result()

try:
    socketio.run(app, port=8080)
except KeyboardInterrupt:
    asyncio.run_coroutine_threadsafe(controllers.clean_up(), loop)
