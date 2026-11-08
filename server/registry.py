"""Room codes, the shared room table and per-connection limits.

Every table (two-seat games and UNO) lives here under a short invite code, so
`/r/<code>` can send a guest to the right page. Starport rooms live in the Node
sidecar; their codes always start with "S", which this table never issues.
"""
import asyncio
import json
import secrets
import time

ALPHABET = '23456789ABCDEFGHJKLMNPQRSTUVWXYZ'
LOCAL_FIRST = ALPHABET.replace('S', '')
CODE_LENGTH = 4
MAX_ROOMS = 2000
IDLE_SECONDS = 1800


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

    async def sweep(self, interval=60):
        """Drop rooms nobody is connected to after IDLE_SECONDS; links stay valid until then."""
        while True:
            await asyncio.sleep(interval)
            now = time.monotonic()
            for room in list(self.rooms.values()):
                if not room.connected() and now - room.updated > IDLE_SECONDS:
                    self.remove(room)


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

    def __init__(self, per_second=30, failed_joins=12):
        self.per_second = per_second
        self.window = time.monotonic()
        self.count = 0
        self.failures = failed_joins

    def allow(self):
        now = time.monotonic()
        if now - self.window >= 1:
            self.window, self.count = now, 0
        self.count += 1
        return self.count <= self.per_second

    def missed_join(self):
        """Returns False once a connection has guessed too many room codes."""
        self.failures -= 1
        return self.failures > 0
