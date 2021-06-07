from __future__ import annotations
import asyncio
import json
import os
from threading import Thread
from typing import TYPE_CHECKING

from flask import Flask, send_from_directory
from flask_socketio import SocketIO, emit

from controller import init_controllers, Controllers


if TYPE_CHECKING:
    from controller import Controller


#TODO: move the whole app out of global state
app = Flask(__name__, static_folder='../frontend/build', static_url_path='/')
socketio = SocketIO(app, cors_allowed_origins="*")


#TODO only supports 1 room at the moment
# need to parameterise the code
@app.route('/bedroom')
def bedroom():
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
    controller: Controller = controllers["Bedroom"]
    queue = controller.queue_state.get_queue_dict()
    emit("message", {"data": json.dumps(queue)})


# TODO: make an abc and use it to define the variants
# shouldn't keep 2 names
class WebSockets:
    def send_queue(self, queue: dict):
        socketio.emit("message", {"data": json.dumps(queue)})

    def clean_up(self):
        pass

def start_background_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()


loop = asyncio.new_event_loop()
t = Thread(target=start_background_loop, args=(loop,), daemon=True)
t.start()

task = asyncio.run_coroutine_threadsafe(init_controllers(WebSockets), loop)
controllers: Controllers = task.result()

try:
    socketio.run(app, port=8080)
except KeyboardInterrupt:
    asyncio.run_coroutine_threadsafe(controllers.clean_up(), loop)
