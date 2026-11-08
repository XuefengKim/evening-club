"""Two-player card games with private per-seat views: crazy eights, palace, six-card golf."""
import random

from . import base
from .base import integer

KINDS=['eights','palace','golf']
SUITS=['spades','hearts','clubs','diamonds']
def rank(card):return card%13+1
def suit(card):return SUITS[card//13]
def strength(card):return 14 if rank(card)==1 else rank(card)
def golf_value(card):
    r=rank(card)
    return -2 if r==2 else 0 if r==13 else min(r,10)
def eights_value(card):return 50 if rank(card)==8 else min(rank(card),10)

class Match(base.Match):
    def __init__(self,kind,first=None,level=1):
        if kind not in KINDS:raise ValueError('请选择一种棋牌游戏')
        self.kind=kind;self.turn=random.randrange(2) if first is None else first
        self.first=self.turn;self.done=False;self.winner=None;self.move=0;self.scores=[0,0]
        self.event={'kind':'start','actor':self.turn};self.note='新牌局开始了'
        self.deck=list(range(52));random.shuffle(self.deck)
        self.pile=[];self.burned=[];self.phase='play';self.ready=[False,False]
        if kind=='eights':
            self.hands=[[self.deck.pop() for _ in range(7)] for p in range(2)]
            # House rule: initial card has no power and is never a special rank.
            i=next(i for i,c in enumerate(self.deck) if rank(c) not in (2,8,12))
            self.pile=[self.deck.pop(i)];self.active_suit=suit(self.pile[-1]);self.passes=0
        elif kind=='palace':
            self.hands=[[self.deck.pop() for _ in range(3)] for p in range(2)]
            self.up=[[self.deck.pop() for _ in range(3)] for p in range(2)]
            self.down=[[self.deck.pop() for _ in range(3)] for p in range(2)]
            self.phase='setup';self.note='可以交换手牌和明牌；满意后点击准备好了'
        else:
            self.layouts=[[self.deck.pop() for _ in range(6)] for p in range(2)]
            self.faceup=[[False]*6 for p in range(2)];self.pile=[self.deck.pop()]
            self.pending=None;self.pending_source=None;self.closer=None
            self.phase='setup';self.note='各自选两张牌翻开，开始前不能偷看暗牌'

    def draw_one(self):
        if not self.deck and len(self.pile)>1:
            top=self.pile[-1];self.deck=self.pile[:-1];self.pile=[top];random.shuffle(self.deck)
        return self.deck.pop() if self.deck else None

    def eights_legal(self,card):
        return rank(card)==8 or suit(card)==self.active_suit or (rank(self.pile[-1])!=8 and rank(card)==rank(self.pile[-1]))

    def palace_legal(self,card):
        return not self.pile or rank(card) in (2,10) or rank(self.pile[-1])==2 or strength(card)>=strength(self.pile[-1])

    def zone(self,actor):
        return 'hand' if self.hands[actor] else 'up' if any(c is not None for c in self.up[actor]) else 'down'

    def golf_score(self,actor,visible_only=False):
        total=0
        for col in range(3):
            a,b=col,col+3
            known_a=not visible_only or self.faceup[actor][a]
            known_b=not visible_only or self.faceup[actor][b]
            if known_a and known_b and rank(self.layouts[actor][a])==rank(self.layouts[actor][b]):continue
            if known_a:total+=golf_value(self.layouts[actor][a])
            if known_b:total+=golf_value(self.layouts[actor][b])
        return total

    def end_golf_turn(self,actor):
        self.pending=None;self.pending_source=None
        if self.closer is not None:
            self.scores=[self.golf_score(p) for p in (0,1)]
            self.finish(-1 if self.scores[0]==self.scores[1] else min((0,1),key=lambda p:self.scores[p]))
            self.note='全部亮牌结算：同列同点数抵消，分数较低者获胜'
        elif all(self.faceup[actor]):
            self.closer=actor;self.note='有一方已全部亮牌，对方还有最后一个完整回合'
        self.turn=1-actor

    def action(self,actor,msg):
        if self.done:raise ValueError('本局已结束，可以再来一局')
        if actor!=self.turn:raise ValueError('请等待自己的回合')
        act=msg.get('act')
        if self.kind=='eights':
            if act=='draw':
                card=self.draw_one()
                if card is not None:self.hands[actor].append(card);self.passes=0;self.note='摸一张牌，本回合结束'
                else:
                    self.passes+=1;self.note='牌库已空，本回合跳过'
                    if self.passes>=2:
                        self.scores=[sum(map(eights_value,h)) for h in self.hands]
                        self.finish(-1 if self.scores[0]==self.scores[1] else min((0,1),key=lambda p:self.scores[p]))
                        self.note='双方连续无牌可摸，按剩余牌罚分较低者获胜'
                self.turn=1-actor;self.emit('draw',actor);return True
            if act!='play':raise ValueError('点选可出的牌，或摸一张')
            card=integer(msg.get('card'),0,51)
            if card not in self.hands[actor] or not self.eights_legal(card):raise ValueError('请选择手中能接点数、花色或万能 8 的牌')
            chosen=msg.get('suit')
            if rank(card)==8 and chosen not in SUITS:raise ValueError('打出 8 时先选择新花色')
            self.hands[actor].remove(card);self.pile.append(card);self.passes=0
            self.active_suit=chosen if rank(card)==8 else suit(card)
            self.turn=1-actor;self.note='接牌成功'
            if not self.hands[actor]:
                self.scores=[sum(map(eights_value,h)) for h in self.hands];self.finish(actor);self.note='率先出完手牌，获胜！'
            elif rank(card)==2:
                for _ in range(2):
                    drawn=self.draw_one()
                    if drawn is not None:self.hands[1-actor].append(drawn)
                self.turn=actor;self.note='2：对方摸两张并跳过，你继续出牌（不叠加）'
            elif rank(card)==12:self.turn=actor;self.note='Q：跳过对方，你继续出牌'
            elif rank(card)==8:self.note='万能 8：新花色已选定'
            if len(self.hands[actor])==1:self.note+=' · 最后一张！（自动提醒）'
            self.emit('play',actor,card=card);return True
        if self.kind=='palace':
            if self.phase=='setup':
                if act=='swap':
                    i=integer(msg.get('hand'),0,len(self.hands[actor])-1);j=integer(msg.get('slot'),0,2)
                    self.hands[actor][i],self.up[actor][j]=self.up[actor][j],self.hands[actor][i]
                    self.note='已交换，仍可调整或点击准备好了';self.emit('swap',actor);return True
                if act!='ready':raise ValueError('先调整明牌，或点击准备好了')
                self.ready[actor]=True
                if all(self.ready):self.phase='play';self.turn=self.first;self.note='先清手牌，再明牌，最后盲翻底牌'
                else:self.turn=1-actor;self.note='轮到另一方调整明牌'
                self.emit('ready',actor);return True
            zone=self.zone(actor)
            if act=='pickup':
                if not self.pile or zone!='hand':raise ValueError('手牌阶段才能直接收堆；明牌或底牌阶段请选一张牌')
                self.hands[actor].extend(self.pile);self.pile=[];self.turn=1-actor
                self.note='收走整堆，对方重新起牌';self.emit('penalty',actor);return True
            if act!='play':raise ValueError('请选择要出的牌')
            if zone=='down':
                i=integer(msg.get('slot'),0,2)
                if self.down[actor][i] is None:raise ValueError('这张底牌已经翻过')
                cards=[self.down[actor][i]]
            else:
                cards=msg.get('cards')
                source=self.hands[actor] if zone=='hand' else self.up[actor]
                if not isinstance(cards,list) or not cards or len(cards)>4 or any(type(c)is not int or c not in source for c in cards) or len(set(cards))!=len(cards) or len({rank(c) for c in cards})!=1:
                    raise ValueError('请选择一张牌，或多张相同点数的牌')
                if zone=='hand' and not self.palace_legal(cards[0]):raise ValueError('手牌接不上，请收走整堆')
            legal=self.palace_legal(cards[0])
            if zone=='down':self.down[actor][i]=None
            else:
                for card in cards:
                    if zone=='hand':self.hands[actor].remove(card)
                    else:self.up[actor][self.up[actor].index(card)]=None
            self.pile.extend(cards)
            if not legal:
                self.hands[actor].extend(self.pile);self.pile=[];self.turn=1-actor
                self.note='翻出的牌接不上：连同整堆收回手中';self.emit('penalty',actor,card=cards[0]);return True
            while len(self.hands[actor])<3 and self.deck:self.hands[actor].append(self.deck.pop())
            burned=rank(cards[0])==10 or (len(self.pile)>=4 and len({rank(c) for c in self.pile[-4:]})==1)
            if burned:self.burned.extend(self.pile);self.pile=[]
            self.turn=actor if burned else 1-actor
            self.note='清掉整堆，继续出牌！' if burned else '已出牌，轮到对方'
            if not self.hands[actor] and not any(c is not None for c in self.up[actor]+self.down[actor]):
                self.finish(actor);self.note='手牌、明牌和底牌全部出完，获胜！'
            self.emit('burn' if burned else 'play',actor,cards=cards);return True
        # Six-card Golf: chosen short-round variant; one final opponent turn.
        if self.phase=='setup':
            if act!='reveal':raise ValueError('先选两张自己的牌翻开')
            i=integer(msg.get('slot'),0,5)
            if self.faceup[actor][i]:raise ValueError('这张牌已经翻开')
            self.faceup[actor][i]=True
            if sum(self.faceup[actor])==2:
                self.ready[actor]=True
                if all(self.ready):self.phase='play';self.turn=self.first;self.note='准备完成，摸牌或拿走弃牌来降低分数'
                else:self.turn=1-actor;self.note='另一方再选两张牌翻开'
            self.emit('flip',actor);return True
        if self.pending is None:
            if act!='draw' or msg.get('source') not in ('deck','pile'):raise ValueError('先从牌库或弃牌堆拿一张')
            source=msg['source']
            if source=='pile':
                if not self.pile:raise ValueError('弃牌堆是空的')
                card=self.pile.pop()
            else:card=self.draw_one()
            if card is None:raise ValueError('牌库暂时没有可摸的牌，请拿弃牌')
            self.pending=card;self.pending_source=source;self.note='选择替换自己的哪一张牌'
            self.emit('draw',actor);return True
        if act=='replace':
            i=integer(msg.get('slot'),0,5)
            self.pile.append(self.layouts[actor][i]);self.layouts[actor][i]=self.pending;self.faceup[actor][i]=True
            self.note='已替换，换下的牌进入弃牌堆'
        elif act=='discard':
            if self.pending_source!='deck':raise ValueError('拿来的弃牌必须用于替换，不能原样丢回')
            i=integer(msg.get('slot'),0,5)
            if self.faceup[actor][i]:raise ValueError('丢弃摸来的牌时，请选一张未翻开的牌亮出')
            self.pile.append(self.pending);self.faceup[actor][i]=True;self.note='弃掉摸来的牌，并翻开所选暗牌'
        else:raise ValueError('请选择替换，或弃牌并亮一张暗牌')
        self.end_golf_turn(actor);self.emit('play',actor);return True

    def public(self,viewer):
        state={'kind':self.kind,'turn':self.turn,'done':self.done,'winner':self.winner,'move':self.move,'event':self.event.copy(),
               'note':self.note,'scores':self.scores[:],'phase':self.phase,'ready':self.ready[:],'deckCount':len(self.deck),
               'top':self.pile[-1] if self.pile else None,'pileCount':len(self.pile)}
        if self.kind in ('eights','palace'):
            state['hand']=self.hands[viewer][:];state['handCounts']=[len(h) for h in self.hands]
            if self.kind=='eights':state.update(activeSuit=self.active_suit,legal=[c for c in self.hands[viewer] if self.eights_legal(c)])
            else:state.update(up=[h[:] for h in self.up],down=[[c is not None for c in h] for h in self.down],zones=[self.zone(p) for p in (0,1)],
                              legal=[c for c in (self.hands[viewer] if self.zone(viewer)=='hand' else self.up[viewer]) if c is not None and self.palace_legal(c)],burnedCount=len(self.burned))
        else:
            state['layouts']=[[c if self.faceup[p][i] or self.done else None for i,c in enumerate(row)] for p,row in enumerate(self.layouts)]
            state['faceup']=[row[:] for row in self.faceup];state['pending']=self.pending if viewer==self.turn else None
            state['pendingSource']=self.pending_source if viewer==self.turn else None;state['closer']=self.closer
            state['scores']=[self.golf_score(p,not self.done) for p in (0,1)]
        return state

    def bot(self,actor):return choose_bot(self.public(actor),actor)

def choose_bot(g,actor):
    """Receives exactly the same information as a human player's client."""
    kind=g['kind']
    if kind=='eights':
        legal=g['legal']
        if not legal:return {'act':'draw'}
        # Retain flexible eights unless they are the last card.
        card=max(legal,key=lambda c:((rank(c)!=8)*100+(rank(c) in (2,12))*20+eights_value(c)))
        remaining=[c for c in g['hand'] if c!=card]
        chosen=max(SUITS,key=lambda s:sum(suit(c)==s for c in remaining))
        return {'act':'play','card':card,'suit':chosen}
    if kind=='palace':
        if g['phase']=='setup':
            hand=g['hand'];up=g['up'][actor]
            def value(c):return 30 if rank(c)==10 else 25 if rank(c)==2 else strength(c)
            hi=max(hand,key=value);j=min(range(3),key=lambda i:value(up[i]))
            if value(hi)>value(up[j]):return {'act':'swap','hand':hand.index(hi),'slot':j}
            return {'act':'ready'}
        zone=g['zones'][actor]
        if zone=='down':return {'act':'play','slot':random.choice([i for i,present in enumerate(g['down'][actor]) if present])}
        legal=g['legal']
        if not legal:
            if zone=='hand':return {'act':'pickup'}
            return {'act':'play','cards':[min((c for c in g['up'][actor] if c is not None),key=strength)]}
        card=min(legal,key=lambda c:30 if rank(c)==10 else 25 if rank(c)==2 else strength(c))
        source=g['hand'] if zone=='hand' else g['up'][actor]
        return {'act':'play','cards':[c for c in source if c is not None and rank(c)==rank(card)]}
    visible=g['layouts'][actor];hidden=[i for i,c in enumerate(visible) if c is None]
    if g['phase']=='setup':return {'act':'reveal','slot':random.choice(hidden)}
    def target(card):
        values=[]
        for i,old in enumerate(visible):
            other=visible[(i+3)%6]
            # Known column pairs should be retained unless a lower value is certain.
            oldpair=old is not None and other is not None and rank(old)==rank(other)
            newpair=other is not None and rank(card)==rank(other)
            gain=(0 if oldpair else (golf_value(old) if old is not None else 5.5)+(golf_value(other) if other is not None else 0))-(0 if newpair else golf_value(card)+(golf_value(other) if other is not None else 0))
            values.append((gain+(0.1 if old is None else 0),i))
        return max(values)
    if g['pending'] is None:
        top=g['top'];take=top is not None and target(top)[0]>2
        return {'act':'draw','source':'pile' if take else 'deck'}
    gain,i=target(g['pending'])
    if g['pendingSource']=='deck' and gain<0 and hidden:return {'act':'discard','slot':random.choice(hidden)}
    return {'act':'replace','slot':i}
