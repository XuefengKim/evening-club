"""Room codes, the shared room table and per-connection limits.

Every table (two-seat games and UNO) lives here under a short invite code, so
`/r/<code>` can send a guest to the right page. Starport rooms live in the Node
sidecar; their codes always start with "S", which this table never issues.
"""
import asyncio
import json
import os
import secrets
import time
from collections import defaultdict, deque

ALPHABET = '23456789ABCDEFGHJKLMNPQRSTUVWXYZ'
LOCAL_FIRST = ALPHABET.replace('S', '')
CODE_LENGTH = 4
MAX_ROOMS = 2000
IDLE_SECONDS = 1800      # a table two people actually used keeps its link this long after everyone drops
ABANDONED_SECONDS = 180  # a table nobody joined or played is reclaimed quickly


def normalize(code):
    code = str(code or '').strip().upper()
    return code if len(code) == CODE_LENGTH and all(c in ALPHABET for c in code) else ''


class Registry:
    def __init__(self):
        self.rooms = {}

    def new_code(self):
        if len(self.rooms) >= MAX_ROOMS:
            raise ValueError('现在开着的牌桌太多了，请稍后再试')
        while True:
            code = secrets.choice(LOCAL_FIRST) + ''.join(secrets.choice(ALPHABET) for _ in range(CODE_LENGTH - 1))
            if code not in self.rooms:
                return code

    def add(self, room):
        self.rooms[room.code] = room
        return room

    def get(self, code):
        return self.rooms.get(normalize(code))

    def remove(self, room):
        if self.rooms.get(room.code) is room:
            del self.rooms[room.code]
            room.close()

    def expired(self, room, now):
        limit = IDLE_SECONDS if room.settled else ABANDONED_SECONDS
        return not room.connected() and now - room.updated > limit

    async def sweep(self, interval=30):
        """Drop rooms nobody is connected to; links of played tables stay valid for IDLE_SECONDS."""
        while True:
            await asyncio.sleep(interval)
            now = time.monotonic()
            for room in list(self.rooms.values()):
                if self.expired(room, now):
                    self.remove(room)
            CREATES.prune()
            MISSES.prune()


registry = Registry()


class Peer:
    """The small socket surface the game code was written against: send(text) and close(code, reason)."""

    def __init__(self, ws):
        self.ws = ws

    async def send(self, text):
        await self.ws.send_str(text)

    async def close(self, code=1000, reason=''):
        await self.ws.close(code=code, message=reason.encode())

    async def error(self, message):
        await self.send(json.dumps({'type': 'error', 'message': message}, ensure_ascii=False))


class Throttle:
    """Per-connection message budget; casual play never comes close."""

    def __init__(self, per_second=30):
        self.per_second = per_second
        self.window = time.monotonic()
        self.count = 0

    def allow(self):
        now = time.monotonic()
        if now - self.window >= 1:
            self.window, self.count = now, 0
        self.count += 1
        return self.count <= self.per_second


class Limiter:
    """Sliding-window counter per client address."""

    def __init__(self, limit, window):
        self.limit, self.window = limit, window
        self.hits = defaultdict(deque)

    def _recent(self, key):
        hits, cutoff = self.hits[key], time.monotonic() - self.window
        while hits and hits[0] < cutoff:
            hits.popleft()
        return hits

    def blocked(self, key):
        return len(self._recent(key)) >= self.limit

    def hit(self, key):
        self._recent(key).append(time.monotonic())

    def allow(self, key):
        if self.blocked(key):
            return False
        self.hit(key)
        return True

    def prune(self):
        for key in list(self.hits):
            if not self._recent(key):
                del self.hits[key]


# Opening tables and guessing codes are budgeted per address, across tables, UNO and Starport.
CREATES = Limiter(30, 600)
MISSES = Limiter(30, 600)
TOO_MANY_TABLES = '这台设备开的牌桌太多了，请过几分钟再试'
TOO_MANY_MISSES = '房间码尝试次数太多，请过几分钟再试，或让朋友重新发一次邀请链接'
# Behind a proxy the socket address is the proxy's. CLIENT_IP_HEADER names a header the edge
# overwrites on every request (Render public services: CF-Connecting-IP). Otherwise
# TRUSTED_PROXY_HOPS counts proxies that each append one X-Forwarded-For entry; the leftmost
# entries can be forged by the caller and are never trusted.
CLIENT_IP_HEADER = os.environ.get('CLIENT_IP_HEADER', '')
PROXY_HOPS = int(os.environ.get('TRUSTED_PROXY_HOPS', '0'))


def client_address(request):
    if CLIENT_IP_HEADER and request.headers.get(CLIENT_IP_HEADER):
        return request.headers[CLIENT_IP_HEADER].strip()
    forwarded = [part.strip() for part in request.headers.get('X-Forwarded-For', '').split(',') if part.strip()]
    if PROXY_HOPS and forwarded:
        return forwarded[-min(PROXY_HOPS, len(forwarded))]
    return request.remote or 'unknown'
