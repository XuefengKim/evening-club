"""UNO tables: each invite code owns its own Game; the rules module is unchanged."""
import json
import time

from aiohttp import WSMsgType

from .games.uno import Game
from .registry import CREATES, MISSES, TOO_MANY_MISSES, TOO_MANY_TABLES, Peer, Throttle, registry


class UnoTable(Game):
    page = '/uno/'

    def __init__(self, code):
        super().__init__()
        self.code = code
        self.updated = time.monotonic()
        self.settled = False

    def add_human(self, name, ws):
        pid = super().add_human(name, ws)
        self.settled = self.settled or len(self.humans) == 2
        return pid

    def start(self, pid):
        result = super().start(pid)
        self.settled = True
        return result

    def connected(self):
        return any(self.players[p]['ws'] is not None for p in self.humans)

    def close(self):
        if self.automation_task: self.automation_task.cancel()

    def state(self, pid):
        return {**super().state(pid), 'room': self.code}

    async def broadcast(self):
        self.updated = time.monotonic()
        await super().broadcast()


ACTIONS = {
    'uno': lambda g, pid, m: g.declare_uno(pid),
    'catchUno': lambda g, pid, m: g.catch_uno(pid),
    'challenge': lambda g, pid, m: g.resolve_challenge(pid, True),
    'openingColor': lambda g, pid, m: g.choose_opening(pid, m.get('color')),
    'play': lambda g, pid, m: g.play(pid, m.get('index'), m.get('color'), m.get('uno', False)),
    'draw': lambda g, pid, m: g.take_card(pid),
    'pass': lambda g, pid, m: g.pass_turn(pid),
}
SETTINGS = {
    'configure': lambda g, pid, m: g.configure(pid, m.get('bots')),
    'rules': lambda g, pid, m: g.set_rules(pid, m.get('stackDrawTwo')),
    'seats': lambda g, pid, m: g.reorder(pid, m.get('order')),
    'shuffleSeats': lambda g, pid, m: g.shuffle_seats(pid),
    'start': lambda g, pid, m: g.start(pid),
}


async def session(ws, address):
    peer, limit = Peer(ws), Throttle()
    game, pid = None, None
    try:
        async for frame in ws:
            if frame.type != WSMsgType.TEXT or not limit.allow(): continue
            try:
                m = json.loads(frame.data)
                if not isinstance(m, dict): continue
                act = m.get('type')
                if pid is None:
                    if act == 'create':
                        if not CREATES.allow(address): raise ValueError(TOO_MANY_TABLES)
                        candidate = UnoTable(registry.new_code())
                    elif act == 'join':
                        if MISSES.blocked(address): raise ValueError(TOO_MANY_MISSES)
                        candidate = registry.get(m.get('room'))
                        if not isinstance(candidate, UnoTable):
                            MISSES.hit(address)
                            raise ValueError('没有找到这一桌，可能已经结束了。请让朋友重新发一次邀请链接')
                    else:
                        continue
                    pid = candidate.add_human(m.get('name', '玩家'), peer)
                    game = registry.add(candidate)
                elif act in SETTINGS:
                    SETTINGS[act](game, pid, m)
                elif act in ACTIONS:
                    if not ACTIONS[act](game, pid, m): continue
                else:
                    continue
                await game.broadcast()
            except (ValueError, TypeError) as exc:
                await peer.error(str(exc))
    finally:
        if pid:
            game.remove_human(pid)
            await game.broadcast()
    return ws
