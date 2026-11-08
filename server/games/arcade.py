"""Classic two-seat games: four in a row, memory, dice, rock-paper-scissors, number bomb, dots and boxes."""
import random
from collections import Counter

from . import base
from .base import integer

KINDS = ['connect', 'memory', 'dice', 'rps', 'number', 'boxes']
MEMORY_LEVELS = {1: (8,4,'初识'), 2: (10,4,'熟悉'), 3: (12,4,'挑战'), 4: (15,5,'高手')}



def four(board, player):
    for r in range(6):
        for c in range(7):
            for dr, dc in [(0, 1), (1, 0), (1, 1), (1, -1)]:
                cells = [(r + dr*i, c + dc*i) for i in range(4)]
                if all(0 <= y < 6 and 0 <= x < 7 and board[y][x] == player for y, x in cells):
                    return cells
    return []

class Match(base.Match):
    def __init__(self, kind, first=None, level=1):
        if kind not in KINDS:
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
