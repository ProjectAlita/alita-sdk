# pip install python-socketio aiohttp

import threading

import socketio
from aiohttp import web
import asyncio

# Create a Socket.IO server
sio = socketio.AsyncServer(cors_allowed_origins=['http://localhost:1420'])
app = web.Application()
sio.attach(app)
remote_app = None


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

@sio.event
async def get_agents(sid, data):
    # find agents to execute
    print('Message from client:', data)
    await sio.emit('message', f"list of agents", room=sid)

@sio.event
async def run_agent(sid, data):
    print('Message from client:', data)
    # //execute agen

    await sio.emit('message', f"Agent's result", room=sid)

def start_socketio_server(): web.run_app(app, host='127.0.0.1', port=5000)


socketio_thread = threading.Thread(target=start_socketio_server)
socketio_thread.daemon = True
socketio_thread.start()


async def send_message_and_wait_for_response(message):
    if remote_app:
        response_future = asyncio.Future()

        @sio.event
        async def mcp(sid, data):
            print("WAITING FOR MESSAGE FOR SID : " + remote_app + " GOT " + sid)
            if sid == remote_app:
                print("MATCHED SID : " + remote_app + " GOT--1 " + sid + " -- " + data)
                response_future.set_result(data)
                print("MATCHED SID : " + remote_app + " GOT--2 " + sid + " -- " + data)

        print("SEND MESSAGE TO SID : " + remote_app)
        await sio.emit('mcp', message, room=remote_app)
        response = await response_future
        return response[0]["content"]
    else:
        return "No client connected."
