"""Two-seat tables for the 15 head-to-head games: seats, reconnection, bot practice and invite links."""
import asyncio
import json
import random
import time

from aiohttp import WSMsgType

from .games import MATCHES
from .registry import Peer, Throttle, registry

KINDS = list(MATCHES)


class Room:
    page = '/'

    def __init__(self, code, kind):
        self.code = code
        self.kind = kind
        self.players = []
        self.match = None
        self.bot_enabled = False
        self.revision = 0
        self.task = None
        self.updated = time.monotonic()
        self.wins = [0, 0]
        self.scored_match = None
        self.match_id = 0
        self.completed = {kind: 0 for kind in KINDS}
        self.memory_mode = 'progressive'
        self.memory_progress = 0

    @property
    def active(self): return self.match is not None and not self.match.done

    @property
    def paused(self): return any(not p['bot'] and p['ws'] is None for p in self.players)

    def connected(self): return any(p['ws'] is not None for p in self.players)

    def close(self):
        if self.task: self.task.cancel()

    def member(self, token): return any(p['token'] == token for p in self.players)

    def join(self, name, token, ws):
        for i, p in enumerate(self.players):
            if p['token'] == token:
                old = p['ws']
                p['ws'] = ws
                if old and old is not ws:
                    asyncio.create_task(old.close(code=4001, reason='已在另一个页面接入'))
                return i
        if self.active: raise ValueError('对方正在玩，等这局结束后就能加入')
        if len(self.players) >= 2: raise ValueError('两个人都已入座，请回到原页面继续')
        self.players.append({'name': str(name).strip()[:12] or '玩家', 'token': token, 'ws': ws, 'bot': False})
        self.wins = [0, 0]
        self.completed = {kind: 0 for kind in KINDS}
        self.memory_progress = 0
        return len(self.players) - 1

    def make_room_for_guest(self):
        """A friend opening the invite link replaces the practice bot between rounds."""
        if not self.active and self.bot_enabled:
            self.players = [p for p in self.players if not p['bot']]
            self.bot_enabled = False
            self.match = None

    def leave(self, seat):
        if self.task: self.task.cancel()
        self.players = [p for i, p in enumerate(self.players) if i != seat and not p['bot']]
        self.match = None
        self.bot_enabled = False
        self.wins = [0, 0]
        self.completed = {kind: 0 for kind in KINDS}
        self.memory_progress = 0

    def host(self, seat):
        if seat != 0: raise ValueError('请先开局的人调整设置')
        if self.active: raise ValueError('本局结束后再调整，先把这局玩完吧')

    def next_memory_level(self):
        return min(1 + self.memory_progress, 4) if self.memory_mode == 'progressive' else int(self.memory_mode)

    def configure(self, seat, msg):
        self.host(seat)
        if msg.get('type') == 'difficulty':
            mode = msg.get('mode')
            if mode not in ['progressive', '1', '2', '3', '4']:
                raise ValueError('请选择循序渐进或固定的四阶难度')
            self.memory_mode = mode
            return
        if msg.get('type') == 'resetProgress':
            self.memory_progress = 0
            return
        if msg.get('type') == 'game':
            if msg.get('game') not in MATCHES: raise ValueError('请选择已有游戏')
            self.kind = msg['game']
        else:
            enabled = msg.get('enabled')
            if type(enabled) is not bool: raise ValueError('请重新选择练习模式')
            if enabled and len(self.players) == 2 and not self.players[1]['bot']:
                raise ValueError('朋友已经入座，不能替换成人机')
            self.players = [p for p in self.players if not p['bot']]
            if enabled:
                self.players.append({'name': '小星 · 人机', 'token': None, 'ws': None, 'bot': True})
            if self.bot_enabled != enabled:
                self.completed = {kind: 0 for kind in KINDS}
                self.memory_progress = 0
            self.bot_enabled = enabled
        self.match = None

    def start(self, seat):
        self.host(seat)
        if len(self.players) != 2 or self.paused: raise ValueError('等朋友连接，或开启人机练习')
        self.match_id += 1
        self.match = MATCHES[self.kind](self.kind, level=self.next_memory_level() if self.kind == 'memory' else 1)

    def state(self, seat):
        return {'type': 'state', 'room': self.code, 'you': seat, 'host': seat == 0, 'kind': self.kind,
                'players': [{'name': p['name'], 'bot': p['bot'], 'online': p['bot'] or p['ws'] is not None} for p in self.players],
                'bot': self.bot_enabled, 'paused': self.paused, 'wins': self.wins[:], 'revision': self.revision,
                'matchId': self.match_id,
                'progression': {'memoryMode': self.memory_mode, 'memoryCompleted': self.memory_progress,
                                'memoryRounds': self.completed['memory'], 'nextMemoryLevel': self.next_memory_level()},
                'game': self.match.public(seat) if self.match else None}

    async def publish(self):
        self.revision += 1
        self.updated = time.monotonic()
        if self.match and self.match.done and self.scored_match is not self.match:
            if self.match.winner in (0, 1): self.wins[self.match.winner] += 1
            self.completed[self.match.kind] += 1
            if self.match.kind == 'memory' and self.memory_mode == 'progressive':
                self.memory_progress = min(self.memory_progress + 1, 3)
            self.scored_match = self.match
        for i, p in enumerate(self.players):
            if p['ws']:
                try: await p['ws'].send(json.dumps(self.state(i), ensure_ascii=False))
                except Exception: pass
        self.schedule()

    def schedule(self):
        current = asyncio.current_task()
        if self.task and self.task is not current: self.task.cancel()
        self.task = None
        if not self.active or self.paused: return
        game = self.match
        transition = (game.kind == 'memory' and game.waiting) or (game.kind == 'rps' and game.revealed)
        bot = next((i for i, p in enumerate(self.players) if p['bot']), None)
        bot_turn = bot is not None and ((game.kind == 'rps' and game.choices[bot] is None and not game.revealed) or (game.kind != 'rps' and game.turn == bot))
        if transition or bot_turn:
            delay = (1.6 if game.kind == 'memory' else 2.6) if transition else random.uniform(2.0, 3.6)
            self.task = asyncio.create_task(self.tick(self.revision, delay, transition, bot))

    async def tick(self, revision, delay, transition, bot):
        await asyncio.sleep(delay)
        if revision != self.revision or self.paused or not self.active: return
        if transition: self.match.transition()
        else: self.match.action(bot, self.match.bot(bot))
        await self.publish()


def seat_token(msg):
    token = msg.get('token')
    if not isinstance(token, str) or not 16 <= len(token) <= 100: raise ValueError('接入信息失效，请刷新页面')
    return token


async def session(ws):
    """One browser tab. First message is create or join; afterwards it acts on that room only."""
    peer, limit = Peer(ws), Throttle()
    room, seat = None, None
    try:
        async for frame in ws:
            if frame.type != WSMsgType.TEXT: continue
            if not limit.allow(): continue
            try:
                msg = json.loads(frame.data)
                if not isinstance(msg, dict): continue
                action = msg.get('type')
                if room is not None:
                    seat = next((i for i, p in enumerate(room.players) if p['ws'] is peer), None)
                    if seat is None: raise ValueError('接入已转移，请在最新页面继续')
                if room is None:
                    if action not in ('create', 'join'): raise ValueError('先选一个游戏，或打开朋友发来的邀请链接')
                    token = seat_token(msg)
                    if action == 'create':
                        kind = msg.get('game', 'connect')
                        if kind not in MATCHES: raise ValueError('请选择已有游戏')
                        candidate = Room(registry.new_code(), kind)
                    else:
                        candidate = registry.get(msg.get('room'))
                        if not isinstance(candidate, Room):
                            if not limit.missed_join():
                                await ws.close(code=4008, message='Too many attempts'.encode())
                                break
                            raise ValueError('没有找到这一桌，可能已经结束了。请让朋友重新发一次邀请链接')
                        if not candidate.member(token): candidate.make_room_for_guest()
                    seat = candidate.join(msg.get('name', '玩家'), token, peer)
                    room = registry.add(candidate)
                elif action == 'leave':
                    room.leave(seat)
                    old, room, seat = room, None, None
                    await peer.send(json.dumps({'type': 'left'}))
                    if old.players: await old.publish()
                    else: registry.remove(old)
                    continue
                elif action in ('game', 'bot', 'difficulty', 'resetProgress'): room.configure(seat, msg)
                elif action == 'start': room.start(seat)
                elif action == 'act':
                    if not room.active: raise ValueError('请先开始一局')
                    if room.paused: raise ValueError('等朋友重新连接，牌局已暂停')
                    room.match.action(seat, msg)
                else: continue
                await room.publish()
            except (ValueError, TypeError, KeyError) as exc:
                await peer.error(str(exc))
    finally:
        if room:
            # Seats can shift after an explicit leave; locate by socket, not stale index.
            for p in room.players:
                if p['ws'] is peer: p['ws'] = None
            await room.publish()
    return ws

