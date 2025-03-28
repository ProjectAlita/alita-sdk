# pip install python-socketio aiohttp

import threading
import socketio
from aiohttp import web
import asyncio

# Create a Socket.IO server
sio = socketio.AsyncServer(cors_allowed_origins=["http://localhost:1420", "http://tauri.localhost"])
app = web.Application()
sio.attach(app)
remote_app = None

def start_socketio_server(): web.run_app(app, host='127.0.0.1', port=5000)

socketio_thread = threading.Thread(target=start_socketio_server)
socketio_thread.daemon = True
socketio_thread.start()

# Define event handlers
@sio.event
async def connect(sid, environ):
    global remote_app
    remote_app = sid
    print('Client connected:', sid)
    await sio.emit('message', {"query": "get_tools", "data": "ASDF"}, room=sid)


@sio.event
async def disconnect(sid):
    global remote_app
    remote_app = None
    print('Client disconnected:', sid)


@sio.event
async def message(sid, data):
    print('Message from client:', data)
    await sio.emit('message', f"Server received: {data}", room=sid)

async def callClient(message):
    if remote_app:
        print("SEND MESSAGE TO SID : " + remote_app)
        response = await sio.call('mcp', message, to=remote_app)

        return response
    else:
        return "No client connected."