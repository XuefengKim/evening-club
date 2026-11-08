"""Board and logic games: tic-tac-toe, gomoku, reversi, nim, hex, code breaker."""
import itertools
import random

from . import base
from .base import integer

KINDS = ['tic', 'gomoku', 'reversi', 'nim', 'hex', 'code']
DIRS = [(r,c) for r in (-1,0,1) for c in (-1,0,1) if r or c]
CODES = [''.join(p) for p in itertools.permutations('012345',3)]

def feedback(secret, guess):
    exact = sum(a == b for a,b in zip(secret,guess))
    return exact, sum(c in secret for c in guess)-exact

class Match(base.Match):
    def __init__(self, kind, first=None, level=1):
        if kind not in KINDS: raise ValueError('请选择新游戏')
        self.kind, self.turn = kind, random.randrange(2) if first is None else first
        self.done, self.winner = False, None
        self.scores, self.move = [0,0], 0
        self.event, self.note = {'kind':'start','actor':self.turn}, '新的一局开始了'
        self.last, self.line = None, []
        if kind in ('tic','gomoku','reversi','hex'):
            self.size = {'tic':3,'gomoku':11,'reversi':6,'hex':5}[kind]
            self.board = [[-1]*self.size for _ in range(self.size)]
            if kind == 'reversi':
                self.board[2][2]=self.board[3][3]=1
                self.board[2][3]=self.board[3][2]=0
                self.count_score()
        elif kind == 'nim': self.piles = [3,5,7]
        else:
            self.secret = random.choice(CODES)
            self.history = []

    def count_score(self):
        self.scores = [sum(row.count(p) for row in self.board) for p in (0,1)]

    def flips(self, r, c, actor):
        n=self.size
        if not (0<=r<n and 0<=c<n) or self.board[r][c]!=-1: return []
        result=[]
        for dr,dc in DIRS:
            y,x=r+dr,c+dc; trail=[]
            while 0<=y<n and 0<=x<n and self.board[y][x]==1-actor:
                trail.append((y,x)); y+=dr; x+=dc
            if trail and 0<=y<n and 0<=x<n and self.board[y][x]==actor: result.extend(trail)
        return result

    def legal(self,actor):
        return [(r,c) for r in range(self.size) for c in range(self.size)
                if self.board[r][c]==-1 and (self.kind!='reversi' or self.flips(r,c,actor))]

    def winning_line(self,r,c,actor):
        required=3 if self.kind=='tic' else 5
        for dr,dc in [(0,1),(1,0),(1,1),(1,-1)]:
            line=[(r,c)]
            for sign in (-1,1):
                y,x=r+sign*dr,c+sign*dc
                while 0<=y<self.size and 0<=x<self.size and self.board[y][x]==actor:
                    line.append((y,x)); y+=sign*dr; x+=sign*dc
            if len(line)>=required:return line
        return []

    def hex_path(self,actor):
        n=self.size
        queue=[(0,c) for c in range(n) if self.board[0][c]==actor] if actor==0 else [(r,0) for r in range(n) if self.board[r][0]==actor]
        parents={p:None for p in queue}
        for r,c in queue:
            if (r if actor==0 else c)==n-1:
                path=[]; p=(r,c)
                while p is not None:path.append(p);p=parents[p]
                return path
            for dr,dc in [(-1,0),(-1,1),(0,-1),(0,1),(1,-1),(1,0)]:
                p=(r+dr,c+dc)
                if 0<=p[0]<n and 0<=p[1]<n and p not in parents and self.board[p[0]][p[1]]==actor:
                    parents[p]=(r,c);queue.append(p)
        return []

    def action(self,actor,msg):
        if self.done:raise ValueError('本局已结束，可以再来一局')
        if actor!=self.turn:raise ValueError('请等待自己的回合')
        if self.kind=='nim':
            if msg.get('act')!='take':raise ValueError('请选择一堆并取走石子')
            pile=integer(msg.get('pile'),0,2)
            count=integer(msg.get('count'),1,self.piles[pile])
            self.piles[pile]-=count
            self.note=f'从第 {pile+1} 堆拿走 {count} 颗'
            if not sum(self.piles):self.finish(actor)
            self.emit('play',actor,pile=pile,count=count)
        elif self.kind=='code':
            guess=msg.get('guess')
            if msg.get('act')!='guess' or type(guess) is not str or guess not in CODES:raise ValueError('请输入三个互不重复的 0–5 数字，例如 024')
            if any(h['guess']==guess for h in self.history):raise ValueError('这个暗码已猜过，请根据线索换一个')
            exact,near=feedback(self.secret,guess)
            self.history.append({'actor':actor,'guess':guess,'exact':exact,'near':near})
            self.note=f'{guess}：{exact} 位正确，{near} 位数字正确但位置不同'
            if exact==3:self.finish(actor)
            self.emit('play',actor)
        else:
            if msg.get('act')!='place':raise ValueError('请选择一个可落子的空位')
            r=integer(msg.get('row'),0,self.size-1);c=integer(msg.get('col'),0,self.size-1)
            if (r,c) not in self.legal(actor):raise ValueError('这里不能落子，请选提示的空位')
            flips=self.flips(r,c,actor) if self.kind=='reversi' else []
            self.board[r][c]=actor;self.last=[r,c]
            for y,x in flips:self.board[y][x]=actor
            if self.kind=='reversi':
                self.count_score();self.note=f'翻转 {len(flips)} 枚棋子'
                if not self.legal(1-actor):
                    if not self.legal(actor):self.finish(-1 if self.scores[0]==self.scores[1] else max((0,1),key=lambda p:self.scores[p]))
                    else:
                        self.turn=1-actor
                        self.note+='；对方无合法落点，自动跳过，由你继续'
            else:
                self.line=self.hex_path(actor) if self.kind=='hex' else self.winning_line(r,c,actor)
                if self.line:self.finish(actor)
                elif not self.legal(1-actor):self.finish(-1)
                self.note='落子完成，下一位准备'
            self.emit('play',actor,row=r,col=c)
        self.turn=1-self.turn
        return True

    def public(self,viewer):
        state={'kind':self.kind,'turn':self.turn,'done':self.done,'winner':self.winner,'scores':self.scores[:],
               'move':self.move,'event':self.event.copy(),'note':self.note}
        if self.kind=='nim':state['piles']=self.piles[:]
        elif self.kind=='code':state.update(history=[h.copy() for h in self.history],secret=self.secret if self.done else None)
        else:state.update(board=[row[:] for row in self.board],size=self.size,last=self.last,line=self.line,
                          legal=[list(p) for p in self.legal(self.turn)] if not self.done else [])
        return state

    def bot(self,actor):
        if self.kind=='nim':
            total=self.piles[0]^self.piles[1]^self.piles[2]
            for i,p in enumerate(self.piles):
                if p^total<p:return {'act':'take','pile':i,'count':p-(p^total)}
            i=random.choice([i for i,p in enumerate(self.piles) if p]);return {'act':'take','pile':i,'count':random.randint(1,self.piles[i])}
        if self.kind=='code':
            candidates=[s for s in CODES if all(feedback(s,h['guess'])==(h['exact'],h['near']) for h in self.history)]
            return {'act':'guess','guess':random.choice(candidates)}
        legal=self.legal(actor)
        if self.kind=='tic':
            def minimax(p):
                opts=self.legal(p)
                if not opts:return 0
                vals=[]
                for r,c in opts:
                    self.board[r][c]=p
                    v=(1 if p==actor else -1) if self.winning_line(r,c,p) else minimax(1-p)
                    self.board[r][c]=-1;vals.append(v)
                return max(vals) if p==actor else min(vals)
            ranked=[]
            for r,c in legal:
                self.board[r][c]=actor
                v=1 if self.winning_line(r,c,actor) else minimax(1-actor)
                self.board[r][c]=-1;ranked.append((v,r,c))
            best=max(v for v,r,c in ranked);r,c=random.choice([(r,c) for v,r,c in ranked if v==best])
        elif self.kind=='reversi':
            def value(p):
                r,c=p;corner=r in (0,5) and c in (0,5)
                return 100*corner+len(self.flips(r,c,actor))+(r in (0,5) or c in (0,5))*3
            r,c=max(legal,key=value)
        elif self.kind=='gomoku':
            for p in (actor,1-actor):
                for r,c in legal:
                    self.board[r][c]=p;win=self.winning_line(r,c,p);self.board[r][c]=-1
                    if win:return {'act':'place','row':r,'col':c}
            def value(p):
                r,c=p;v=-(abs(r-5)+abs(c-5))*.15
                for dr,dc in DIRS:
                    for d in (1,2):
                        y,x=r+dr*d,c+dc*d
                        if 0<=y<11 and 0<=x<11 and self.board[y][x]!=-1:v+=3/d
                return v+random.random()*.3
            r,c=max(legal,key=value)
        else:
            for p in (actor,1-actor):
                for r,c in legal:
                    self.board[r][c]=p;win=self.hex_path(p);self.board[r][c]=-1
                    if win:return {'act':'place','row':r,'col':c}
            def value(p):
                r,c=p
                return sum(0<=r+dr<5 and 0<=c+dc<5 and self.board[r+dr][c+dc]==actor for dr,dc in [(-1,0),(-1,1),(0,-1),(0,1),(1,-1),(1,0)])*2-abs((c if actor==0 else r)-2)*.4+random.random()
            r,c=max(legal,key=value)
        return {'act':'place','row':r,'col':c}
