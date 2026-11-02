"""A local two-seat arcade. All moves and hidden information are owned by the server."""
import asyncio
import json
import os
import random
import secrets
import signal
import socket
import time
from collections import Counter
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.parse import urlsplit
from websockets.asyncio.server import serve

ROOT = Path(__file__).parent
GAMES = ['connect', 'memory', 'dice', 'rps', 'number', 'boxes']
MEMORY_LEVELS = {1: (8,4,'初识'), 2: (10,4,'熟悉'), 3: (12,4,'挑战'), 4: (15,5,'高手')}


def integer(v, low, high):
    if type(v) is not int or not low <= v <= high:
        raise ValueError('请使用当前界面上可选的操作')
    return v


def four(board, player):
    for r in range(6):
        for c in range(7):
            for dr, dc in [(0, 1), (1, 0), (1, 1), (1, -1)]:
                cells = [(r + dr*i, c + dc*i) for i in range(4)]
                if all(0 <= y < 6 and 0 <= x < 7 and board[y][x] == player for y, x in cells):
                    return cells
    return []


class Match:
    def __init__(self, kind, first=None, level=1):
        if kind not in GAMES:
            raise ValueError('请选择已有游戏')
        self.kind = kind
        self.turn = random.randrange(2) if first is None else first
        self.done = False
        self.winner = None
        self.scores = [0, 0]
        self.move = 0
        self.event = {'kind': 'start', 'actor': self.turn}
        self.note = '新的一局开始了'
        if kind == 'connect':
            self.board = [[-1]*7 for _ in range(6)]
            self.line = []
            self.last = None
        elif kind == 'memory':
            self.level = integer(level,1,4)
            self.pairs, self.columns, self.level_name = MEMORY_LEVELS[self.level]
            self.cards = list(range(self.pairs))*2
            random.shuffle(self.cards)
            self.matched = [-1]*len(self.cards)
            self.open = []
            self.seen = {}
            self.waiting = False
        elif kind == 'dice':
            self.bank = 0
            self.die = None
            self.rolls = []
        elif kind == 'rps':
            self.choices = [None, None]
            self.revealed = False
            self.round = 1
        elif kind == 'number':
            self.secret = random.randint(1, 99)
            self.low, self.high = 0, 100
            self.history = []
        else:
            # 4x4 dots, 24 edges, 9 boxes.
            self.edges = [-1]*24
            self.boxes = [-1]*9
            self.last = None

    def emit(self, kind, actor=None, **extra):
        self.move += 1
        self.event = {'kind': kind, 'actor': actor, **extra}

    def finish(self, winner):
        self.done = True
        self.winner = winner

    def box_edges(self, box):
        r, c = divmod(box, 3)
        return [r*3+c, (r+1)*3+c, 12+r*4+c, 12+r*4+c+1]

    def action(self, actor, msg):
        if self.done:
            raise ValueError('本局已结束，可以再来一局')
        if self.kind != 'rps' and actor != self.turn:
            raise ValueError('请等待自己的回合')
        act = msg.get('act')
        if self.kind == 'connect':
            if act != 'drop': raise ValueError('请点一列落子')
            col = integer(msg.get('col'), 0, 6)
            rows = [r for r in range(6) if self.board[r][col] == -1]
            if not rows: raise ValueError('这一列已满，换一列吧')
            row = max(rows)
            self.board[row][col] = actor
            self.last = [row, col]
            self.line = four(self.board, actor)
            if self.line: self.finish(actor)
            elif all(x != -1 for x in self.board[0]): self.finish(-1)
            self.turn = 1-actor
            self.note = '一枚棋子，新的可能'
            self.emit('drop', actor, row=row, col=col)
        elif self.kind == 'memory':
            if act != 'flip' or self.waiting: raise ValueError('等这两张牌翻回去再选')
            i = integer(msg.get('index'), 0, len(self.cards)-1)
            if self.matched[i] != -1 or i in self.open: raise ValueError('选一张还没翻开的牌')
            self.open.append(i)
            self.seen[i] = self.cards[i]
            self.emit('flip', actor, index=i)
            if len(self.open) == 2:
                a, b = self.open
                if self.cards[a] == self.cards[b]:
                    self.matched[a] = self.matched[b] = actor
                    self.scores[actor] += 1
                    self.open = []
                    self.note = '找到一对！继续翻牌'
                    self.emit('pair', actor, indices=[a, b])
                    if all(v != -1 for v in self.matched):
                        self.finish(-1 if self.scores[0] == self.scores[1] else max(range(2), key=lambda p:self.scores[p]))
                else:
                    self.waiting = True
                    self.note = '记住它们的位置，下一位准备'
            else: self.note = '再选一张，找到相同图案'
        elif self.kind == 'dice':
            if act == 'roll':
                self.die = random.randint(1, 6)
                self.rolls.append(self.die)
                if self.die == 1:
                    self.note = f'掷出了 1，本回合暂存分归零'
                    self.bank = 0
                    self.turn = 1-actor
                    self.emit('bust', actor, die=1)
                else:
                    self.bank += self.die
                    self.note = f'暂存 {self.bank} 分：继续冒险，还是见好就收？'
                    self.emit('roll', actor, die=self.die)
            elif act == 'bank':
                if self.bank <= 0: raise ValueError('先掷一次骰子吧')
                value = self.bank
                self.scores[actor] += value
                self.bank = 0
                self.turn = 1-actor
                self.note = f'稳稳收下 {value} 分'
                self.emit('bank', actor, count=value)
                if self.scores[actor] >= 50: self.finish(actor)
            else: raise ValueError('请选择掷骰子或收分')
            if self.turn != actor: self.rolls = []
        elif self.kind == 'rps':
            if act != 'choose' or self.revealed: raise ValueError('下一回合马上开始')
            value = msg.get('choice')
            if value not in ['rock', 'paper', 'scissors']: raise ValueError('请选择石头、布或剪刀')
            if self.choices[actor] is not None: raise ValueError('已锁定，等对方选择')
            self.choices[actor] = value
            self.note = '选择已锁定，等双方一起揭晓'
            self.emit('lock', actor)
            if all(self.choices):
                self.revealed = True
                a, b = self.choices
                if a == b: winner = -1
                else: winner = 0 if (a, b) in [('rock','scissors'),('scissors','paper'),('paper','rock')] else 1
                if winner != -1: self.scores[winner] += 1
                self.note = '默契平局！再试一次' if winner == -1 else '这一回合的胜负揭晓了'
                self.emit('reveal', winner)
                if max(self.scores) >= 3: self.finish(max(range(2), key=lambda i:self.scores[i]))
        elif self.kind == 'number':
            if act != 'guess': raise ValueError('请输入安全范围内的整数')
            n = integer(msg.get('number'), self.low+1, self.high-1)
            hit = n == self.secret
            self.history.append({'actor':actor,'number':n,'hit':hit})
            self.emit('explode' if hit else 'safe', actor, number=n)
            if hit:
                self.note = f'隐藏数字是 {n}！踩中数字的人落败'
                self.finish(1-actor)
            else:
                if n < self.secret: self.low = n
                else: self.high = n
                self.turn = 1-actor
                self.note = f'{n} 安全。现在只能选 {self.low+1}–{self.high-1}'
        else:
            if act != 'edge': raise ValueError('请选择一条空边')
            edge = integer(msg.get('edge'), 0, 23)
            if self.edges[edge] != -1: raise ValueError('这条边已经被画过了')
            self.edges[edge] = actor
            self.last = edge
            completed = []
            for box in range(9):
                if self.boxes[box] == -1 and all(self.edges[i] != -1 for i in self.box_edges(box)):
                    self.boxes[box] = actor
                    self.scores[actor] += 1
                    completed.append(box)
            self.note = '围成方格，得分并继续画线！' if completed else '画一条边，等待时机'
            self.emit('box' if completed else 'edge', actor, edge=edge, boxes=completed)
            if not completed: self.turn = 1-actor
            if all(v != -1 for v in self.boxes):
                self.finish(max(range(2), key=lambda p:self.scores[p]))
        return True

    def transition(self):
        if self.kind == 'memory' and self.waiting:
            self.open = []
            self.waiting = False
            self.turn = 1-self.turn
            self.note = '轮到下一位，记忆接力'
            self.emit('turn', self.turn)
        elif self.kind == 'rps' and self.revealed and not self.done:
            self.round += 1
            self.choices = [None, None]
            self.revealed = False
            self.note = '新回合，藏好你的选择'
            self.emit('round')
        else: return False
        return True

    def public(self, viewer):
        state = {'kind':self.kind,'turn':self.turn,'done':self.done,'winner':self.winner,
                 'scores':self.scores[:],'move':self.move,'event':self.event,'note':self.note}
        if self.kind == 'connect': state.update(board=self.board,line=self.line,last=self.last)
        elif self.kind == 'memory':
            state.update(cards=[v if i in self.open or self.matched[i] != -1 else None for i,v in enumerate(self.cards)],
                         owners=self.matched[:],open=self.open[:],waiting=self.waiting,
                         level=self.level,pairs=self.pairs,columns=self.columns,levelName=self.level_name)
        elif self.kind == 'dice': state.update(bank=self.bank,die=self.die,rolls=self.rolls[-8:],goal=50)
        elif self.kind == 'rps': state.update(choices=self.choices[:] if self.revealed else [v if i==viewer else None for i,v in enumerate(self.choices)],locked=[v is not None for v in self.choices],revealed=self.revealed,round=self.round)
        elif self.kind == 'number': state.update(low=self.low,high=self.high,history=self.history[-8:],secret=self.secret if self.done else None)
        else: state.update(edges=self.edges[:],boxes=self.boxes[:],last=self.last)
        return state

    def bot(self, actor):
        if self.kind == 'connect':
            legal = [c for c in range(7) if self.board[0][c] == -1]
            for p in [actor, 1-actor]:
                for col in legal:
                    row = max(r for r in range(6) if self.board[r][col] == -1)
                    self.board[row][col] = p
                    win = bool(four(self.board,p))
                    self.board[row][col] = -1
                    if win: return {'act':'drop','col':col}
            return {'act':'drop','col':random.choice(sorted(legal,key=lambda c:abs(3-c))[:3])}
        if self.kind == 'memory':
            available = [i for i in range(len(self.cards)) if self.matched[i] == -1 and i not in self.open]
            if self.open:
                known = [i for i in available if self.seen.get(i) == self.seen[self.open[0]]]
            else:
                counts = Counter(v for i,v in self.seen.items() if self.matched[i] == -1)
                known = [i for i in available if i in self.seen and counts[self.seen[i]] >= 2]
            unknown = [i for i in available if i not in self.seen]
            return {'act':'flip','index':random.choice(known or unknown or available)}
        if self.kind == 'dice':
            safe = self.bank >= 14 or (self.bank > 0 and self.scores[actor]+self.bank >= 50)
            return {'act':'bank' if safe else 'roll'}
        if self.kind == 'rps': return {'act':'choose','choice':random.choice(['rock','paper','scissors'])}
        if self.kind == 'number': return {'act':'guess','number':random.randint(self.low+1,self.high-1)}
        legal = [i for i,v in enumerate(self.edges) if v == -1]
        close, safe = [], []
        for edge in legal:
            adjacent = [self.box_edges(b) for b in range(9) if edge in self.box_edges(b)]
            filled = [sum(self.edges[i] != -1 for i in edges) for edges in adjacent]
            if 3 in filled: close.append(edge)
            if 2 not in filled: safe.append(edge)
        return {'act':'edge','edge':random.choice(close or safe or legal)}


class Room:
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
        self.completed = {kind:0 for kind in GAMES}
        self.memory_mode = 'progressive'
        self.memory_progress = 0

    @property
    def active(self): return self.match is not None and not self.match.done

    @property
    def paused(self): return any(not p['bot'] and p['ws'] is None for p in self.players)

    def join(self, name, token, ws):
        for i,p in enumerate(self.players):
            if p['token'] == token:
                old = p['ws']
                p['ws'] = ws
                if old and old is not ws:
                    asyncio.create_task(old.close(code=4001,reason='已在另一个页面接入'))
                return i
        if self.active: raise ValueError('对方正在玩，等这局结束后就能加入')
        if len(self.players) >= 2: raise ValueError('两个人都已入座，请回到原页面继续')
        self.players.append({'name':str(name).strip()[:12] or '玩家','token':token,'ws':ws,'bot':False})
        self.wins = [0,0]
        self.completed = {kind:0 for kind in GAMES}
        self.memory_progress = 0
        return len(self.players)-1

    def host(self, seat):
        if seat != 0: raise ValueError('请先开局的人调整设置')
        if self.active: raise ValueError('本局结束后再调整，先把这局玩完吧')

    def next_memory_level(self):
        return min(1+self.memory_progress,4) if self.memory_mode=='progressive' else int(self.memory_mode)

    def configure(self, seat, msg):
        self.host(seat)
        if msg.get('type') == 'difficulty':
            mode=msg.get('mode')
            if mode not in ['progressive','1','2','3','4']:
                raise ValueError('请选择循序渐进或固定的四阶难度')
            self.memory_mode=mode
            return
        if msg.get('type') == 'resetProgress':
            self.memory_progress=0
            return
        if msg.get('type') == 'game':
            if msg.get('game') not in GAMES: raise ValueError('请选择已有游戏')
            self.kind = msg['game']
        else:
            enabled = msg.get('enabled')
            if type(enabled) is not bool: raise ValueError('请重新选择练习模式')
            if enabled and len(self.players) == 2 and not self.players[1]['bot']:
                raise ValueError('朋友已经入座，不能替换成人机')
            self.players = [p for p in self.players if not p['bot']]
            if enabled:
                self.players.append({'name':'小星 · 人机','token':None,'ws':None,'bot':True})
            if self.bot_enabled != enabled:
                self.completed = {kind:0 for kind in GAMES}
                self.memory_progress = 0
            self.bot_enabled = enabled
        self.match = None

    def start(self, seat):
        self.host(seat)
        if len(self.players) != 2 or self.paused: raise ValueError('等朋友连接，或开启人机练习')
        self.match_id += 1
        self.match = Match(self.kind,level=self.next_memory_level() if self.kind=='memory' else 1)

    def state(self, seat):
        return {'type':'state','room':self.code,'you':seat,'host':seat==0,'kind':self.kind,
                'players':[{'name':p['name'],'bot':p['bot'],'online':p['bot'] or p['ws'] is not None} for p in self.players],
                'bot':self.bot_enabled,'paused':self.paused,'wins':self.wins[:],'revision':self.revision,
                'matchId':self.match_id,'progression':{'memoryMode':self.memory_mode,'memoryCompleted':self.memory_progress,'memoryRounds':self.completed['memory'],'nextMemoryLevel':self.next_memory_level()},'game':self.match.public(seat) if self.match else None}

    async def publish(self):
        self.revision += 1
        self.updated = time.monotonic()
        if self.match and self.match.done and self.scored_match is not self.match:
            if self.match.winner in (0,1): self.wins[self.match.winner] += 1
            self.completed[self.match.kind] += 1
            if self.match.kind=='memory' and self.memory_mode=='progressive':
                self.memory_progress=min(self.memory_progress+1,3)
            self.scored_match = self.match
        for i,p in enumerate(self.players):
            if p['ws']:
                try: await p['ws'].send(json.dumps(self.state(i),ensure_ascii=False))
                except Exception: pass
        self.schedule()

    def schedule(self):
        current = asyncio.current_task()
        if self.task and self.task is not current: self.task.cancel()
        self.task = None
        if not self.active or self.paused: return
        game = self.match
        transition = (game.kind=='memory' and game.waiting) or (game.kind=='rps' and game.revealed)
        bot = next((i for i,p in enumerate(self.players) if p['bot']),None)
        bot_turn = bot is not None and ((game.kind=='rps' and game.choices[bot] is None and not game.revealed) or (game.kind!='rps' and game.turn==bot))
        if transition or bot_turn:
            delay = (1.6 if game.kind=='memory' else 2.6) if transition else random.uniform(2.0,3.6)
            self.task = asyncio.create_task(self.tick(self.revision,delay,transition,bot))

    async def tick(self, revision, delay, transition, bot):
        await asyncio.sleep(delay)
        if revision != self.revision or self.paused or not self.active: return
        if transition: self.match.transition()
        else: self.match.action(bot,self.match.bot(bot))
        await self.publish()


rooms = {}

def current_table():
    active=[r for r in list(rooms.values()) if any(not p['bot'] and p['ws'] is not None for p in r.players)]
    return max(active,key=lambda r:r.updated) if active else None

def discovery():
    room=current_table()
    if not room:return {'available':False}
    humans=[p for p in room.players if not p['bot']]
    can_join=not room.active and (len(room.players)<2 or room.bot_enabled)
    return {'available':True,'game':room.kind,'host':humans[0]['name'],
            'canJoin':can_join,'playing':room.active,'occupied':len(humans)}



async def handler(ws):
    room, seat = None, None
    try:
        async for raw in ws:
            try:
                msg = json.loads(raw)
                if not isinstance(msg,dict): continue
                action = msg.get('type')
                if room is not None:
                    seat = next((i for i,p in enumerate(room.players) if p['ws'] is ws),None)
                    if seat is None: raise ValueError('接入已转移，请在最新页面继续')
                if room is None:
                    if action not in ('create','join','joinCurrent'): raise ValueError('先选一个游戏，或加入对方的牌桌')
                    token = msg.get('token')
                    if not isinstance(token,str) or not 16 <= len(token) <= 100: raise ValueError('接入信息失效，请刷新页面')
                    existing=current_table()
                    if action=='joinCurrent' or (action=='create' and existing):
                        candidate=existing
                        if not candidate:raise ValueError('对方还没开局，选一个游戏开始吧')
                        if not candidate.active and candidate.bot_enabled:
                            candidate.players=[p for p in candidate.players if not p['bot']]
                            candidate.bot_enabled=False
                            candidate.match=None
                        seat=candidate.join(msg.get('name','朋友'),token,ws)
                        room=candidate
                        await room.publish()
                        continue
                    if action == 'create':
                        kind = msg.get('game','connect')
                        if kind not in GAMES: raise ValueError('请选择已有游戏')
                        code = ''.join(secrets.choice('23456789ABCDEFGHJKLMNPQRSTUVWXYZ') for _ in range(4))
                        while code in rooms: code = ''.join(secrets.choice('23456789ABCDEFGHJKLMNPQRSTUVWXYZ') for _ in range(4))
                        candidate = Room(code,kind)
                    else:
                        code = str(msg.get('room','')).strip().upper()
                        candidate = rooms.get(code)
                        if not candidate: raise ValueError('游戏厅已更新，请在首页直接加入或重新开一局')
                    seat = candidate.join(msg.get('name','玩家'),token,ws)
                    room = candidate
                    rooms[room.code] = room
                elif action == 'leave':
                    if room.task: room.task.cancel()
                    humans = [p for i,p in enumerate(room.players) if i != seat and not p['bot']]
                    room.players = humans
                    room.match = None
                    room.bot_enabled = False
                    room.wins = [0,0]
                    room.completed = {kind:0 for kind in GAMES}
                    room.memory_progress = 0
                    old = room
                    room, seat = None,None
                    await ws.send(json.dumps({'type':'left'}))
                    if humans: await old.publish()
                    else: rooms.pop(old.code,None)
                    continue
                elif action in ('game','bot','difficulty','resetProgress'): room.configure(seat,msg)
                elif action == 'start': room.start(seat)
                elif action == 'act':
                    if not room.active: raise ValueError('请先开始一局')
                    if room.paused: raise ValueError('等朋友重新连接，牌局已暂停')
                    room.match.action(seat,msg)
                else: continue
                await room.publish()
            except (ValueError,TypeError,KeyError) as exc:
                await ws.send(json.dumps({'type':'error','message':str(exc)},ensure_ascii=False))
    finally:
        if room:
            # Seats can shift after an explicit leave; locate by socket, not stale index.
            for p in room.players:
                if p['ws'] is ws: p['ws'] = None
            await room.publish()


class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*args,**kw):super().__init__(*args,directory=str(ROOT),**kw)
    def do_GET(self):
        if urlsplit(self.path).path=='/api/table':
            data=json.dumps(discovery(),ensure_ascii=False).encode()
            self.send_response(200)
            self.send_header('Content-Type','application/json; charset=utf-8')
            self.send_header('Content-Length',str(len(data)))
            self.end_headers();self.wfile.write(data);return
        if urlsplit(self.path).path not in ('/','/index.html','/style.css','/app.js','/audio.js','/favicon.svg','/guide.txt'):
            self.send_error(404);return
        super().do_GET()
    def end_headers(self):
        self.send_header('Cache-Control','no-cache');super().end_headers()
    def log_message(self,*args):pass


async def cleanup():
    while True:
        await asyncio.sleep(60)
        now=time.monotonic()
        for code,room in list(rooms.items()):
            if not any(p['ws'] for p in room.players) and now-room.updated>1800:
                if room.task:room.task.cancel()
                rooms.pop(code,None)


async def main():
    http_port=int(os.environ.get('ARCADE_HTTP_PORT','8780'))
    ws_port=int(os.environ.get('ARCADE_WS_PORT','8781'))
    http=ThreadingHTTPServer((os.environ.get('GAME_BIND','127.0.0.1'),http_port),Handler)
    Thread(target=http.serve_forever,daemon=True).start()
    print('双人游戏厅已启动：')
    try:
        ips={x[4][0] for x in socket.getaddrinfo(socket.gethostname(),None,socket.AF_INET) if not x[4][0].startswith('127.')}
    except OSError:ips=set()
    for ip in sorted(ips):print(f'http://{ip}:{http_port}')
    janitor=asyncio.create_task(cleanup())
    stop=asyncio.Event()
    loop=asyncio.get_running_loop()
    for sig in (signal.SIGINT,signal.SIGTERM):
        try:loop.add_signal_handler(sig,stop.set)
        except (NotImplementedError,RuntimeError):pass
    pidfile=ROOT/'server.pid'
    try:
        async with serve(handler,os.environ.get('GAME_BIND','127.0.0.1'),ws_port,max_size=4096):
            pidfile.write_text(str(os.getpid()))
            await stop.wait()
    finally:
        janitor.cancel()
        http.shutdown()
        if pidfile.exists() and pidfile.read_text().strip()==str(os.getpid()):pidfile.unlink()


if __name__=='__main__':asyncio.run(main())
