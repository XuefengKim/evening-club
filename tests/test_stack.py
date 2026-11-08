"""End-to-end checks against the real launcher on an isolated port: every game through one origin."""
import asyncio
import json
import os
from pathlib import Path
import re
import signal
import socket
import subprocess
import sys
import tempfile
import time

import aiohttp
from yarl import URL

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from server.games import MATCHES  # noqa: E402

PAGES = ['/', '/play/connect', '/play/golf', '/uno/', '/starport/']
ASSETS = ['/favicon.svg', '/shared/club.css', '/shared/club.js', '/shared/catalog.js', '/shared/audio.js',
          '/play/app.js', '/play/arcade.js', '/play/board.js', '/play/cards.js', '/uno/uno.css', '/uno/uno.js',
          '/starport/client.mjs', '/starport/engine.mjs', '/starport/view.mjs', '/starport/style.css',
          '/starport/manifest.webmanifest', '/starport/icon-192.png', '/starport/icon-512.png']
PRIVATE = ['/start.py', '/.env', '/server/app.py', '/starport/server.mjs', '/../requirements.txt', '/.data/starport-progress.json',
           '/%2e%2e/start.py', '/play/nope', '/tests/test_stack.py',
           '/shared///club.css', '/shared/./club.css', '/shared/.//club.css']


def free_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


class Client:
    def __init__(self, ws):
        self.ws, self.inbox = ws, []

    async def send(self, **m):
        await self.ws.send_str(json.dumps(m))

    async def receive(self, predicate=lambda m: m.get('type') == 'state', allow_error=False):
        for m in self.inbox:
            if predicate(m):
                self.inbox.remove(m)
                return m
        while True:
            frame = await asyncio.wait_for(self.ws.receive(), 5)
            if frame.type != aiohttp.WSMsgType.TEXT:
                raise AssertionError(f'socket closed: {frame.type} {frame.data}')
            m = json.loads(frame.data)
            if m.get('type') == 'error' and not allow_error:
                raise AssertionError(m.get('message'))
            if predicate(m):
                return m


async def client(http, base, route):
    return Client(await http.ws_connect(base + route, max_msg_size=0))


async def tables(http, base):
    token = lambda c: c * 32
    for kind in MATCHES:
        a, b = await client(http, base, '/ws/table'), await client(http, base, '/ws/table')
        await a.send(type='create', game=kind, token=token('a'), name='Player A')
        code = (await a.receive())['room']
        async with http.get(f'{base}/r/{code}', allow_redirects=False) as r:
            assert r.headers['Location'] == f'/?r={code}', r.headers['Location']
        await b.send(type='join', room=code.lower(), token=token('b'), name='Player B')
        await a.receive(lambda m: m.get('type') == 'state' and len(m['players']) == 2)
        await b.receive()
        await a.send(type='start')
        x = await a.receive(lambda m: m.get('type') == 'state' and m.get('game') is not None)
        y = await b.receive(lambda m: m.get('type') == 'state' and m.get('game') is not None)
        assert x['kind'] == y['kind'] == kind and x['room'] == y['room'] == code
        assert x['game']['move'] == y['game']['move']
        await a.send(type='leave'); await a.receive(lambda m: m.get('type') == 'left')
        await b.send(type='leave'); await b.receive(lambda m: m.get('type') == 'left')
        await a.ws.close(); await b.ws.close()
        print('PASS two-client invite table:', kind)


async def isolation(http, base):
    """Strangers never land on each other's table; a full table refuses a third player."""
    a, b, c = [await client(http, base, '/ws/table') for _ in range(3)]
    await a.send(type='create', game='connect', token='a' * 32, name='A')
    await b.send(type='create', game='connect', token='b' * 32, name='B')
    ra, rb = (await a.receive())['room'], (await b.receive())['room']
    assert ra != rb
    await c.send(type='join', room=ra, token='c' * 32, name='C')
    await c.receive(); await a.receive(lambda m: len(m['players']) == 2)
    d = await client(http, base, '/ws/table')
    await d.send(type='join', room=ra, token='d' * 32, name='D')
    err = await d.receive(lambda m: m.get('type') == 'error', allow_error=True)
    assert '已入座' in err['message']
    await d.send(type='join', room='ZZZZ', token='d' * 32, name='D')
    err = await d.receive(lambda m: m.get('type') == 'error', allow_error=True)
    assert '没有找到' in err['message']
    # Practice bot gives way when a friend opens the invite link.
    await b.send(type='bot', enabled=True)
    assert [p['bot'] for p in (await b.receive(lambda m: len(m['players']) == 2))['players']] == [False, True]
    e = await client(http, base, '/ws/table')
    await e.send(type='join', room=rb, token='e' * 32, name='E')
    state = await e.receive()
    assert [p['bot'] for p in state['players']] == [False, False] and state['you'] == 1
    # A reload reclaims the same seat with the same token; the old tab is told why it closed.
    a2 = await client(http, base, '/ws/table')
    await a2.send(type='join', room=ra, token='a' * 32, name='A')
    assert (await a2.receive())['you'] == 0
    frame = await asyncio.wait_for(a.ws.receive(), 5)
    while frame.type == aiohttp.WSMsgType.TEXT:
        frame = await asyncio.wait_for(a.ws.receive(), 5)
    assert a.ws.close_code == 4001, a.ws.close_code
    for x in (a2, b, c, d, e):
        await x.ws.close()
    print('PASS separate rooms, full-table refusal, unknown code, bot replaced by invited friend, seat reclaim')


async def uno(http, base):
    a, b = await client(http, base, '/ws/uno'), await client(http, base, '/ws/uno')
    await a.send(type='create', name='Player A')
    code = (await a.receive())['room']
    async with http.get(f'{base}/r/{code}', allow_redirects=False) as r:
        assert r.headers['Location'] == f'/uno/?r={code}'
    await b.send(type='join', room=code, name='Player B')
    await b.receive()
    await a.send(type='configure', bots=0)
    await a.send(type='start')
    await a.receive(lambda m: m.get('type') == 'state' and m.get('started'))
    await b.receive(lambda m: m.get('type') == 'state' and m.get('started'))
    other = await client(http, base, '/ws/uno')
    await other.send(type='create', name='Elsewhere')
    assert (await other.receive())['room'] != code
    for x in (a, b, other):
        await x.ws.close()
    print('PASS two-client UNO table by invite; separate tables stay separate')


async def starport(http, base):
    a, b = await client(http, base, '/ws/starport'), await client(http, base, '/ws/starport')
    await a.send(type='create', player='a' * 32)
    joined = await a.receive(lambda m: m.get('type') == 'joined')
    code = joined['room']
    async with http.get(f'{base}/r/{code}', allow_redirects=False) as r:
        assert r.headers['Location'] == f'/starport/?r={code}'
    await b.send(type='join', room=code, player='b' * 32)
    assert (await b.receive(lambda m: m.get('type') == 'joined'))['role'] == 1
    await a.send(type='start')
    await a.receive(lambda m: m.get('type') == 'state' and m.get('started') and not m['paused'])
    await a.send(type='input', right=True)
    await b.receive(lambda m: m.get('type') == 'state' and m['game']['players'][0]['x'] > 70)
    again = await client(http, base, '/ws/starport')
    await again.send(type='join', room=code, token=joined['token'], player='a' * 32)
    assert (await again.receive(lambda m: m.get('type') == 'joined'))['role'] == 0
    frame = await asyncio.wait_for(a.ws.receive(), 5)
    while frame.type == aiohttp.WSMsgType.TEXT:
        frame = await asyncio.wait_for(a.ws.receive(), 5)
    assert a.ws.close_code == 4001, a.ws.close_code
    await again.send(type='leave'); await b.send(type='leave')
    await again.ws.close(); await b.ws.close()
    print('PASS Starport room through the relay: invite, independent movement, seat takeover close code')


async def http_checks(http, base):
    for route in PAGES + ASSETS:
        async with http.get(base + route) as r:
            assert r.status == 200, route
    async with http.get(base + '/shared/club.css', headers={'Accept-Encoding': 'gzip'}) as r:
        assert r.headers.get('Content-Encoding') == 'gzip' and r.headers['X-Content-Type-Options'] == 'nosniff'
        etag = r.headers['ETag']
    async with http.get(base + '/shared/club.css', headers={'If-None-Match': etag}) as r:
        assert r.status == 304
    async with http.get(base + '/starport/manifest.webmanifest') as r:
        manifest = await r.json(content_type=None)
        assert manifest['scope'] == './' and manifest['start_url'].startswith('./')
    for route in PRIVATE:  # sent verbatim: the client must not tidy '//' or './' before the server sees them
        async with http.get(URL(base + route, encoded=True), allow_redirects=False) as r:
            assert r.status == 404, (route, r.status)
    for route, target in [('/extra/', '/'), ('/cards/', '/'), ('/play', '/'), ('/uno', '/uno/'), ('/r/ZZZZ', '/?missing=ZZZZ'), ('/r/bad!', '/')]:
        async with http.get(base + route, allow_redirects=False) as r:
            assert r.status in (301, 302) and r.headers['Location'] == target, (route, r.headers.get('Location'))
    try:
        await http.ws_connect(base + '/ws/table', headers={'Origin': 'https://evil.example'})
    except aiohttp.WSServerHandshakeError as exc:
        assert exc.status == 403
    else:
        raise AssertionError('Cross-origin socket accepted')
    async with http.get(base + '/_health') as r:
        assert (await r.json())['ok'] is True
    print('PASS pages and assets on one origin, gzip + ETag, private paths hidden, legacy redirects, origin check')


async def budgets(http, base):
    """One address cannot fill the server with tables or brute-force room codes (runs last: it spends the budget)."""
    refused = None
    for _ in range(40):
        c = await client(http, base, '/ws/table')
        await c.send(type='create', game='connect', token='z' * 32, name='Z')
        m = await c.receive(lambda m: m.get('type') in ('state', 'error'), allow_error=True)
        await c.ws.close()
        if m['type'] == 'error':
            refused = m['message']
            break
    assert refused and '太多' in refused, refused
    s = await client(http, base, '/ws/starport')
    await s.send(type='create', player='z' * 32)
    assert '太多' in (await s.receive(lambda m: m.get('type') == 'error', allow_error=True))['message']
    await s.ws.close()
    c = await client(http, base, '/ws/table')
    for _ in range(40):
        await c.send(type='join', room='ZZZZ', token='z' * 32, name='Z')
        m = await c.receive(lambda m: m.get('type') == 'error', allow_error=True)
        if '尝试次数太多' in m['message']:
            break
    else:
        raise AssertionError('code guessing was never limited')
    await c.ws.close()
    print('PASS per-address budgets: table flood refused (tables and Starport), code guessing limited')


async def hello(http, base):
    s = await client(http, base, '/ws/starport')
    await s.send(type='hello', player='a' * 32)
    m = await s.receive(lambda m: m.get('type') == 'hello')
    assert m['room'] is None and 'unlocked' in m['progress'] and m['game']['level'] == 0
    await s.ws.close()
    print('PASS Starport welcome screen gets this browser\'s progress before taking a seat')


async def protocols(port):
    base = f'http://127.0.0.1:{port}'
    async with aiohttp.ClientSession() as http:
        await http_checks(http, base)
        await tables(http, base)
        await isolation(http, base)
        await uno(http, base)
        await starport(http, base)
        await hello(http, base)
        await budgets(http, base)


def main():
    port = free_port()
    data = tempfile.mkdtemp(prefix='club-test-')
    p = subprocess.Popen([sys.executable, str(ROOT / 'start.py'), '--bind', '127.0.0.1', '--port', str(port)],
                         env=dict(os.environ, DATA_DIR=data), cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    lines = []
    try:
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            line = p.stdout.readline()
            if not line:
                raise AssertionError('Launcher exited:\n' + ''.join(lines))
            lines.append(line)
            if '17 games ready' in line:
                break
        else:
            raise AssertionError('Stack readiness timeout')
        sidecar = int(re.search(r'127\.0\.0\.1:(\d+)', ''.join(lines)).group(1))
        asyncio.run(protocols(port))
        print('PASS all 17 games reachable on one origin')
    finally:
        if p.poll() is None:
            p.send_signal(signal.SIGTERM)
        try:
            p.wait(timeout=10)
        except subprocess.TimeoutExpired:
            p.kill(); p.wait(); raise
        p.stdout.close()
    time.sleep(.3)
    for check in (port, sidecar):
        with socket.socket() as s:
            assert s.connect_ex(('127.0.0.1', check)) != 0, f'Leaked listener on {check}'
    print('PASS launcher stops the app and the Starport sidecar')


if __name__ == '__main__':
    main()
