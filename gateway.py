"""One LAN origin for every game page, discovery API and WebSocket."""
import asyncio
import mimetypes
import os
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import urlopen
from websockets.asyncio.server import serve
from websockets.asyncio.client import connect
from websockets.http11 import Response
from websockets.datastructures import Headers

ROOT = Path(__file__).resolve().parent / 'apps'
PORT = int(os.environ.get('CLUB_GATEWAY_PORT', '8780'))
BIND = os.environ.get('CLUB_GATEWAY_BIND', '0.0.0.0')
WS_PORTS = {f'/ws/{name}': int(os.environ[f'CLUB_{name.upper()}_WS'])
            for name in ('arcade', 'extra', 'uno', 'cards', 'starport')}
API_PORTS = {'/api/table': int(os.environ['CLUB_ARCADE_HTTP']),
             '/extra/api/table': int(os.environ['CLUB_EXTRA_HTTP']),
             '/cards/api/table': int(os.environ['CLUB_CARDS_HTTP'])}
ASSETS = {'index.html', 'app.js', 'audio.js', 'style.css', 'favicon.svg'}
STARPORT_ASSETS = {'index.html', 'client.mjs', 'engine.mjs', 'view.mjs', 'style.css',
                   'favicon.svg', 'manifest.webmanifest', 'icon-192.png', 'icon-512.png'}

def response(code, body, mime='text/plain; charset=utf-8', extra=()):
    names = {200:'OK', 301:'Moved Permanently', 404:'Not Found', 405:'Method Not Allowed', 502:'Bad Gateway'}
    return Response(code, names[code], Headers([
        ('Content-Type', mime), ('Content-Length', str(len(body))),
        ('Cache-Control', 'no-store'), ('X-Content-Type-Options', 'nosniff'), *extra]), body)

async def process_request(conn, req):
    path = urlsplit(req.path).path
    if req.headers.get('Upgrade', '').lower() == 'websocket':
        return None if path in WS_PORTS else response(404, b'Unknown socket')
    if path == '/_health':
        return response(200, b'{"ok":true}', 'application/json')
    if path in API_PORTS:
        try:
            def fetch():
                with urlopen(f'http://127.0.0.1:{API_PORTS[path]}/api/table', timeout=3) as r:
                    return r.read()
            return response(200, await asyncio.to_thread(fetch), 'application/json; charset=utf-8')
        except Exception:
            return response(502, b'Game backend unavailable')
    for name in ('extra', 'uno', 'cards', 'starport'):
        if path == '/' + name:
            return response(301, b'', extra=[('Location', '/' + name + '/')])
    parts = path.strip('/').split('/')
    section = parts[0] if parts[0] in ('extra', 'uno', 'cards', 'starport') else 'main'
    relative = '/'.join(parts[1:] if section != 'main' else parts) or 'index.html'
    if relative not in (STARPORT_ASSETS if section == 'starport' else ASSETS):
        return response(404, b'Not found')
    file = ROOT / section / relative
    if not file.is_file():
        return response(404, b'Not found')
    mime = {'.mjs':'text/javascript', '.webmanifest':'application/manifest+json'}.get(file.suffix)
    mime = mime or mimetypes.guess_type(file.name)[0] or 'application/octet-stream'
    if mime.startswith('text/') or mime in ('application/javascript', 'application/manifest+json'):
        mime += '; charset=utf-8'
    return response(200, file.read_bytes(), mime)

async def bridge(ws):
    port = WS_PORTS[urlsplit(ws.request.path).path]
    try:
        async with connect(f'ws://127.0.0.1:{port}', proxy=None, max_size=1048576) as upstream:
            async def pump(source, destination):
                async for message in source:
                    await destination.send(message)
            tasks = [asyncio.create_task(pump(ws, upstream)), asyncio.create_task(pump(upstream, ws))]
            _, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for task in pending:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
    except Exception:
        await ws.close(code=1011, reason='Game connection unavailable')

async def main():
    async with serve(bridge, BIND, PORT, process_request=process_request, max_size=1048576):
        print(f'Game gateway: http://{BIND}:{PORT}/', flush=True)
        await asyncio.Future()

if __name__ == '__main__':
    asyncio.run(main())
