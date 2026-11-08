"""One public origin for the whole arcade.

aiohttp serves the pages, the invite redirect and two WebSocket endpoints
(`/ws/table` for the 15 head-to-head games, `/ws/uno`). Starport Crew keeps its
Node server because its physics engine is shared with the browser; it runs as a
private child process on the loopback interface and `/ws/starport` is relayed to it.
"""
import asyncio
import os
import shutil
import socket
import sys
from pathlib import Path
from urllib.parse import urlsplit

import aiohttp
from aiohttp import web

from . import table, uno_table
from .registry import normalize, registry
from .static import SECURITY, Static

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / 'web'
STARPORT = ROOT / 'starport'
MAX_MESSAGE = 4096
PAGES = {'/': 'index.html', '/uno/': 'uno/index.html', '/starport/': 'starport/index.html'}
# Section URLs from the LAN version keep working; a #game fragment survives the redirect.
REDIRECTS = {'/play': '/', '/play/': '/', '/extra': '/', '/extra/': '/', '/cards': '/', '/cards/': '/', '/uno': '/uno/', '/starport': '/starport/'}


def same_origin(request):
    origin = request.headers.get('Origin')
    if not origin:
        return True
    return urlsplit(origin).netloc == request.host


async def accept(request):
    if not same_origin(request):
        raise web.HTTPForbidden(text='Origin mismatch')
    ws = web.WebSocketResponse(max_msg_size=MAX_MESSAGE, heartbeat=25)
    await ws.prepare(request)
    return ws


async def table_socket(request):
    return await table.session(await accept(request))


async def uno_socket(request):
    return await uno_table.session(await accept(request))


async def starport_socket(request):
    client = await accept(request)
    sidecar = request.app['starport']
    try:
        async with request.app['http'].ws_connect(f'ws://127.0.0.1:{sidecar.port}/', max_msg_size=MAX_MESSAGE) as upstream:
            async def downstream():
                async for frame in upstream:
                    if frame.type == aiohttp.WSMsgType.TEXT:
                        await client.send_str(frame.data)
            async def uplink():
                async for frame in client:
                    if frame.type == aiohttp.WSMsgType.TEXT:
                        await upstream.send_str(frame.data)
            tasks = [asyncio.create_task(downstream()), asyncio.create_task(uplink())]
            await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            code = upstream.close_code
            if code and 4000 <= code < 5000:
                await client.close(code=code, message=b'Connected elsewhere')
    except aiohttp.ClientError:
        await client.close(code=1011, message=b'Starport unavailable')
    if not client.closed:
        await client.close()
    return client


async def invite(request):
    """/r/CODE opens whichever page owns the room."""
    code = normalize(request.match_info['code'])
    if code.startswith('S'):
        raise web.HTTPFound(f'/starport/?r={code}')
    room = registry.get(code)
    if room is None:
        raise web.HTTPFound(f'/?missing={code}' if code else '/')
    raise web.HTTPFound(f'{room.page}?r={code}')


async def health(request):
    alive = request.app['starport'].alive()
    return web.json_response({'ok': alive, 'rooms': len(registry.rooms)}, status=200 if alive else 503)


async def page(request):
    path, files = request.path, request.app['static']
    if path in REDIRECTS:
        raise web.HTTPMovedPermanently(REDIRECTS[path] + (f'?{request.query_string}' if request.query_string else ''))
    if path in PAGES:
        return files.response(request, PAGES[path])
    if path.startswith('/play/') and path[6:] in table.MATCHES:
        return files.response(request, PAGES['/'])  # /play/<game> opens that game's table setup
    return files.response(request, path.lstrip('/'))


class Starport:
    """Supervises the Node sidecar; restarts it if it ever exits."""

    def __init__(self, data):
        self.data = data
        self.port = free_port()
        self.process = None
        self.watch = None
        self.stopping = False

    def alive(self):
        return self.process is not None and self.process.returncode is None

    async def spawn(self):
        node = shutil.which('node')
        env = dict(os.environ, PORT=str(self.port), GAME_BIND='127.0.0.1', PROGRESS_FILE=str(self.data / 'starport-progress.json'))
        self.process = await asyncio.create_subprocess_exec(node, str(STARPORT / 'server.mjs'), cwd=str(STARPORT), env=env)
        for _ in range(600):
            if self.process.returncode is not None:
                raise RuntimeError('Starport server stopped during startup')
            if port_open(self.port):
                return
            await asyncio.sleep(.1)
        raise RuntimeError('Starport server did not start within 60 seconds')

    async def supervise(self):
        while not self.stopping:
            await self.process.wait()
            if self.stopping:
                return
            print(f'Starport server exited ({self.process.returncode}); restarting', file=sys.stderr, flush=True)
            await asyncio.sleep(1)
            await self.spawn()

    async def start(self):
        await self.spawn()
        self.watch = asyncio.create_task(self.supervise())

    async def stop(self):
        self.stopping = True
        if self.watch:
            self.watch.cancel()
        if self.alive():
            self.process.terminate()
            try:
                await asyncio.wait_for(self.process.wait(), 5)
            except asyncio.TimeoutError:
                self.process.kill()
                await self.process.wait()


def free_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def port_open(port):
    with socket.socket() as s:
        return s.connect_ex(('127.0.0.1', port)) == 0


@web.middleware
async def headers(request, handler):
    response = await handler(request)
    for key, value in SECURITY.items():
        response.headers.setdefault(key, value)
    return response


def create_app(data_dir=None):
    data = Path(data_dir or os.environ.get('DATA_DIR') or ROOT / '.data')
    data.mkdir(parents=True, exist_ok=True)
    app = web.Application(middlewares=[headers])
    app['static'] = Static(WEB)
    app['starport'] = Starport(data)

    async def lifecycle(app):
        app['http'] = aiohttp.ClientSession()
        await app['starport'].start()
        sweeper = asyncio.create_task(registry.sweep())
        yield
        sweeper.cancel()
        await app['starport'].stop()
        await app['http'].close()

    app.cleanup_ctx.append(lifecycle)
    app.router.add_get('/_health', health)
    app.router.add_get('/ws/table', table_socket)
    app.router.add_get('/ws/uno', uno_socket)
    app.router.add_get('/ws/starport', starport_socket)
    app.router.add_get('/r/{code}', invite)
    app.router.add_get('/{tail:.*}', page)
    return app


def run(host='0.0.0.0', port=8780, on_ready=None):
    async def ready(app):
        if on_ready:
            on_ready()
    app = create_app()
    app.on_startup.append(ready)
    web.run_app(app, host=host, port=port, print=None, access_log=None, handle_signals=True, shutdown_timeout=3)


if __name__ == '__main__':
    run(port=int(os.environ.get('PORT', '8780')))
