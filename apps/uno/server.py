import asyncio
import os
import json
import random
import socket
import uuid
from collections import Counter
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from websockets.asyncio.server import serve

ROOT = Path(__file__).parent
COLORS = ['red', 'yellow', 'green', 'blue']


def freshdeck():
    cards = []
    for color in COLORS:
        cards.append({'c': color, 'v': '0'})
        for value in [*map(str, range(1, 10)), 'skip', 'reverse', '+2']:
            cards.extend([{'c': color, 'v': value} for _ in range(2)])
    for value in ['wild', '+4']:
        cards.extend([{'c': 'black', 'v': value} for _ in range(4)])
    random.shuffle(cards)
    return cards


class Game:
    def __init__(self):
        self.players = {}
        self.host_id = None
        self.stack_draw_two = False
        self.pending_penalty = 0
        self.number_finish = True
        self.drawn_index = None
        self.uno_ready = set()
        self.uno_announced = set()
        self.uno_vulnerable = None
        self.challenge = None
        self.challenge_result = None
        self.opening_wild = None
        self.dealer = None
        self.scores = {}
        self.match_winner = None
        self.round_points = 0
        self.hands = {}
        self.deck = []
        self.discard = []
        self.turn = 0
        self.direction = 1
        self.color = None
        self.started = False
        self.winner = None
        self.pending_draw = False
        self.bot_count = 0
        self.message = '等待玩家入座'
        self.revision = 0
        self.event = None
        self.automation_task = None

    @property
    def humans(self):
        return [p for p in self.players if not self.players[p]['bot']]

    @property
    def host(self):
        return self.host_id if self.host_id in self.humans else next(iter(self.humans), None)

    @property
    def current(self):
        return list(self.players)[self.turn] if self.started and self.players else None

    def emit(self, kind, actor=None, target=None, count=0):
        self.revision += 1
        self.event = {'id': self.revision, 'kind': kind, 'actor': actor,
                      'target': target, 'count': count}

    def require_lobby_host(self, pid):
        if pid != self.host or (self.started and not self.winner):
            raise ValueError('只有房主可在开局前或本局结束后调整设置')

    def set_rules(self, pid, stack):
        self.require_lobby_host(pid)
        if type(stack) is not bool:
            raise ValueError('叠加规则必须为开启或关闭')
        self.stack_draw_two = stack
        self.message = '+2 叠加已' + ('开启：只接 +2，不限颜色；+4 不参与' if stack else '关闭：罚牌后跳过回合')
        self.emit('config', pid)

    def reorder(self, pid, order):
        self.require_lobby_host(pid)
        if not isinstance(order, list) or any(not isinstance(p, str) for p in order) or len(order) != len(self.players) or set(order) != set(self.players):
            raise ValueError('座位列表已变化，请按当前玩家重新排列')
        self.players = {p: self.players[p] for p in order}
        self.message = '座位顺序已更新，按下方顺序顺时针出牌'
        self.emit('seats', pid)

    def shuffle_seats(self, pid):
        self.require_lobby_host(pid)
        order = list(self.players)
        random.shuffle(order)
        self.reorder(pid, order)

    def configure(self, pid, count):
        if pid != self.host or (self.started and not self.winner):
            raise ValueError('只有房主可在开局前或本局结束后设置人机')
        if type(count) is not int or not 0 <= count <= 3:
            raise ValueError('人机数量请选择 0、1、2 或 3')
        for p in list(self.players):
            if self.players[p]['bot']:
                del self.players[p]
                self.hands.pop(p, None)
        self.started = False
        self.winner = None
        self.turn = 0
        self.pending_penalty = 0
        self.pending_draw = False
        self.clear_choices()
        self.scores = {p: 0 for p in self.players}
        self.match_winner = None
        self.discard = []
        self.color = None
        for p in self.humans:
            self.hands[p] = []
        self.bot_count = count
        for i in range(count):
            p = 'bot-' + str(i + 1)
            self.players[p] = {'name': ['小橙', '阿蓝', '小松'][i] + ' · 人机', 'bot': True, 'ws': None}
            self.hands[p] = []
        self.message = f'已设置 {count} 个人机' if count else '双人模式，等待两位朋友'
        self.emit('config', pid)

    def add_human(self, name, ws):
        if self.started and not self.winner:
            raise ValueError('本局正在进行，请等本局结束后加入')
        if len(self.humans) >= 2:
            raise ValueError('两个人类座位已满')
        pid = uuid.uuid4().hex[:12]
        self.players[pid] = {'name': str(name).strip()[:16] or '玩家', 'bot': False, 'ws': ws}
        self.hands[pid] = []
        self.scores[pid] = 0
        if self.host_id is None:
            self.host_id = pid
        self.message = f"{self.players[pid]['name']} 入座了"
        self.emit('join', pid)
        return pid

    def remove_human(self, pid):
        if pid not in self.players:
            return
        del self.players[pid]
        if self.host_id == pid:
            self.host_id = next(iter(self.humans), None)
        self.pending_penalty = 0
        self.clear_choices()
        self.scores.pop(pid, None)
        self.match_winner = None
        self.hands.pop(pid, None)
        self.started = False
        self.winner = None
        self.pending_draw = False
        self.turn = 0
        self.color = None
        self.discard = []
        for p in self.players:
            self.hands[p] = []
        if not self.humans:
            self.players.clear()
            self.hands.clear()
            self.bot_count = 0
        self.message = '朋友离开了牌桌，请重新开始'
        self.emit('leave', pid)

    def draw(self):
        if not self.deck and len(self.discard) > 1:
            top = self.discard[-1]
            self.deck = self.discard[:-1]
            random.shuffle(self.deck)
            self.discard = [top]
        return self.deck.pop() if self.deck else None

    def playable(self, card):
        if self.pending_penalty:
            return card['v'] == '+2'
        return bool(self.discard) and (card['c'] == 'black' or card['c'] == self.color or card['v'] == self.discard[-1]['v'])

    def next_index(self, steps=1):
        return (self.turn + self.direction * steps) % len(self.players)

    def start(self, pid):
        self.require_lobby_host(pid)
        if len(self.players) < 2:
            raise ValueError('至少需要两位玩家，可添加人机后单人开局')
        ids = list(self.players)
        if self.match_winner:
            self.scores = {p: 0 for p in ids}
            self.match_winner = None
        self.round_points = 0
        self.clear_choices()
        self.deck = freshdeck()
        self.discard = []
        self.hands = {p: [self.draw() for _ in range(7)] for p in ids}
        self.dealer = ids[(ids.index(self.dealer) + 1) % len(ids)] if self.dealer in ids else random.choice(ids)
        self.turn = (ids.index(self.dealer) + 1) % len(ids)
        self.direction = 1
        self.pending_penalty = 0
        self.started = True
        self.winner = None
        self.pending_draw = False
        first = self.draw()
        while first['v'] == '+4':
            self.deck.insert(0, first)
            random.shuffle(self.deck)
            first = self.draw()
        self.discard = [first]
        self.color = first['c'] if first['c'] in COLORS else None
        self.message = f"{self.players[self.dealer]['name']} 发牌，游戏开始！"
        if first['v'] == 'wild':
            self.opening_wild = self.current
            self.message = '起手翻到变色牌，请首位玩家选择颜色'
        elif first['v'] == 'skip':
            self.turn = self.next_index()
            self.message = '起手跳过牌，首位玩家被跳过'
        elif first['v'] == 'reverse':
            self.direction = -1
            self.turn = ids.index(self.dealer)
            self.message = '起手反转，发牌者先出，按逆时针进行'
        elif first['v'] == '+2':
            if self.stack_draw_two:
                self.pending_penalty = 2
                self.message = '起手 +2，首位玩家可接 +2 或接受罚牌'
            else:
                target = self.current
                for _ in range(2):
                    self.hands[target].append(self.draw())
                self.turn = self.next_index()
                self.message = f"起手 +2，{self.players[target]['name']} 摸2张并跳过"
        self.emit('deal', pid)

    def clear_choices(self):
        self.drawn_index = None
        self.uno_ready.clear()
        self.uno_announced.clear()
        self.uno_vulnerable = None
        self.challenge = None
        self.challenge_result = None
        self.opening_wild = None

    def legal_moves(self, pid):
        if self.challenge or self.opening_wild:
            return []
        hand = self.hands.get(pid, [])
        valid = []
        for i, card in enumerate(hand):
            if self.number_finish and len(hand) == 1 and not card['v'].isdigit():
                continue
            if pid == self.current and self.pending_draw and i != self.drawn_index:
                continue
            if self.playable(card):
                valid.append(i)
        return valid

    def expire_uno(self, actor):
        # Catch window closes when the next player begins an actual game action.
        self.uno_vulnerable = None
        self.uno_ready.discard(actor)

    def deal_cards(self, pid, count):
        actual = 0
        for _ in range(count):
            card = self.draw()
            if card:
                self.hands[pid].append(card)
                actual += 1
        self.uno_ready.discard(pid)
        self.uno_announced.discard(pid)
        if self.uno_vulnerable == pid:
            self.uno_vulnerable = None
        return actual

    def declare_uno(self, pid):
        if not self.started or self.winner or pid not in self.players:
            return False
        if (len(self.hands[pid]) == 2 and self.can_act(pid) and not self.challenge and not self.opening_wild) or self.uno_vulnerable == pid:
            self.uno_ready.add(pid)
            if self.uno_vulnerable == pid:
                self.uno_vulnerable = None
                self.uno_announced.add(pid)
            self.message = f"{self.players[pid]['name']} 喊了 UNO！"
            self.emit('uno', pid)
            return True
        return False

    def catch_uno(self, pid):
        target = self.uno_vulnerable
        if not self.started or self.winner or pid not in self.players or not target or pid == target:
            return False
        count = self.deal_cards(target, 2)
        self.uno_vulnerable = None
        self.message = f"{self.players[target]['name']} 漏喊 UNO，被抓到，罚摸 {count} 张"
        self.emit('catch', pid, target, count)
        return True

    def choose_opening(self, pid, color):
        if not self.can_act(pid) or self.opening_wild != pid or color not in COLORS:
            return False
        self.color = color
        self.opening_wild = None
        self.message = f"{self.players[pid]['name']} 选择颜色后继续出牌"
        self.emit('wild', pid)
        return True

    def finish_round(self, pid):
        self.winner = pid
        def points(card):
            return int(card['v']) if card['v'].isdigit() else 50 if card['c'] == 'black' else 20
        self.round_points = sum(points(c) for p, hand in self.hands.items() if p != pid for c in hand)
        self.scores[pid] = self.scores.get(pid, 0) + self.round_points
        self.message = f"{self.players[pid]['name']} 获胜，本局 +{self.round_points} 分，累计 {self.scores[pid]} 分"
        if self.scores[pid] >= 500:
            self.match_winner = pid
            self.message += '，赢得500分赛！'

    def resolve_challenge(self, pid, challenge=False):
        if not self.can_act(pid) or not self.challenge or self.challenge['target'] != pid:
            return False
        info = self.challenge
        self.expire_uno(pid)
        self.challenge = None
        if challenge:
            self.challenge_result = {'id': self.revision + 1, 'viewer': pid, 'actor': info['actor'], 'hand': info['hand'], 'color': info['color'], 'success': info['illegal']}
        if challenge and info['illegal']:
            target, amount = info['actor'], 4
            self.message = f"质疑成功，{self.players[target]['name']} 罚摸4张；质疑者正常出牌"
        else:
            target, amount = pid, 6 if challenge else 4
            self.message = f"质疑失败，罚摸6张并跳过" if challenge else f"{self.players[pid]['name']} 接受 +4 并跳过回合"
            self.turn = self.next_index()
        count = self.deal_cards(target, amount)
        self.pending_draw = False
        self.drawn_index = None
        self.emit('challenge' if challenge else 'penalty', pid, target, count)
        return True

    def can_act(self, pid):
        return self.started and not self.winner and pid == self.current

    def settle_penalty(self, pid):
        if not self.can_act(pid) or not self.pending_penalty:
            return False
        self.expire_uno(pid)
        self.drawn_index = None
        total, actual = self.pending_penalty, 0
        for _ in range(total):
            card = self.draw()
            if card:
                self.hands[pid].append(card)
                actual += 1
        self.pending_penalty = 0
        self.pending_draw = False
        self.uno_announced.discard(pid)
        self.turn = self.next_index()
        self.message = f"{self.players[pid]['name']} 接受累计 {total} 张罚牌，摸到 {actual} 张，跳过回合"
        self.emit('penalty', pid, pid, actual)
        return True

    def take_card(self, pid, automatic=False):
        if self.challenge:
            return self.resolve_challenge(pid, False)
        if self.opening_wild:
            return False
        if self.pending_penalty:
            return self.settle_penalty(pid)
        if not self.can_act(pid) or self.pending_draw:
            return False
        self.expire_uno(pid)
        card = self.draw()
        if card:
            self.hands[pid].append(card)
            self.uno_announced.discard(pid)
            self.drawn_index = len(self.hands[pid]) - 1
            self.pending_draw = True
            self.message = f"{self.players[pid]['name']} {'无可出牌，自动' if automatic else ''}摸了一张牌；本回合只能出刚摸到的牌"
            self.emit('draw', pid, pid, 1)
        elif not any(self.legal_moves(p) for p in self.players):
            self.started = False
            self.message = '牌堆已空，所有人都无法出牌，本局和局'
            self.emit('tie', pid)
        else:
            self.pass_turn(pid, force=True)
        return True

    def pass_turn(self, pid, force=False):
        if self.challenge or self.opening_wild or self.pending_penalty or not self.can_act(pid) or (not self.pending_draw and not force):
            return False
        self.expire_uno(pid)
        self.drawn_index = None
        self.turn = self.next_index()
        self.pending_draw = False
        self.message = f"{self.players[pid]['name']} 结束回合，轮到 {self.players[self.current]['name']}"
        self.emit('pass', pid, self.current)
        return True

    def play(self, pid, index, chosen=None, announce=False):
        if not self.can_act(pid) or type(index) is not int or not 0 <= index < len(self.hands[pid]):
            return False
        if type(announce) is not bool or (announce and len(self.hands[pid]) != 2):
            return False
        card = self.hands[pid][index]
        if index not in self.legal_moves(pid) or (card['c'] == 'black' and chosen not in COLORS):
            return False
        declared = pid in self.uno_ready or announce
        prior_color = self.color
        illegal_four = card['v'] == '+4' and any(c['c'] == prior_color for j, c in enumerate(self.hands[pid]) if j != index)
        self.expire_uno(pid)
        self.drawn_index = None
        self.hands[pid].pop(index)
        self.uno_announced.discard(pid)
        if len(self.hands[pid]) == 1 and declared:
            self.uno_announced.add(pid)
        if len(self.hands[pid]) == 1 and not declared:
            self.uno_vulnerable = pid
        self.discard.append(card)
        self.color = chosen if card['c'] == 'black' else card['c']
        self.pending_draw = False
        value = card['v']
        target = list(self.players)[self.next_index()]
        kind, count = 'play', 0
        if value == '+2' and self.stack_draw_two and self.hands[pid]:
            self.pending_penalty += 2
            count = self.pending_penalty
            kind = 'stack'
            self.turn = self.next_index()
            self.message = f"{self.players[pid]['name']} 出了 +2，累计 {count} 张；下家可接 +2 或接受罚牌"
        elif value == '+4':
            kind = 'four'
            self.challenge = {'actor': pid, 'target': target, 'illegal': illegal_four, 'color': prior_color, 'hand': [dict(c) for c in self.hands[pid]]}
            self.turn = self.next_index()
            self.message = f"{self.players[pid]['name']} 出了 +4；下家可接受4张或质疑"
        elif value == '+2':
            kind = 'penalty'
            total = (self.pending_penalty + 2) if value == '+2' else 4
            self.pending_penalty = 0
            for _ in range(total):
                extra = self.draw()
                if extra:
                    self.hands[target].append(extra)
                    count += 1
            self.turn = self.next_index(2)
            self.message = f"{self.players[pid]['name']} 出了 {value}，{self.players[target]['name']} 摸 {count} 张并跳过"
        elif value == 'reverse':
            kind = 'reverse'
            self.direction *= -1
            if len(self.players) > 2:
                self.turn = self.next_index()
            self.message = f"{self.players[pid]['name']} 反转了出牌方向" if len(self.players) > 2 else f"{self.players[pid]['name']} 反转，继续出牌"
        elif value == 'skip':
            kind = 'skip'
            self.turn = self.next_index(2)
            self.message = f"{self.players[pid]['name']} 跳过了 {self.players[target]['name']}"
        else:
            kind = 'wild' if value == 'wild' else 'play'
            self.turn = self.next_index()
            self.message = f"{self.players[pid]['name']} 出了 {'变色牌' if value == 'wild' else value}"
        if not self.hands[pid]:
            self.finish_round(pid)
        if len(self.hands[pid]) == 1 and declared:
            self.message += ' · UNO！'
        self.emit(kind, pid, target, count)
        return True

    def automation_needed(self):
        if not self.started or self.winner:
            return False
        if self.players[self.current]['bot']:
            return True
        if self.challenge or self.opening_wild:
            return False
        return not self.legal_moves(self.current)

    def auto_step(self):
        if not self.automation_needed():
            return False
        pid = self.current
        bot = self.players[pid]['bot']
        if bot and self.uno_vulnerable and self.uno_vulnerable != pid:
            return self.catch_uno(pid)
        colors = Counter(c['c'] for c in self.hands[pid] if c['c'] in COLORS)
        chosen = max(COLORS, key=lambda c: colors[c])
        if self.opening_wild:
            return self.choose_opening(pid, chosen)
        if self.challenge:
            # Bot cannot inspect the private legality/evidence in the challenge.
            return self.resolve_challenge(pid, random.random() < .25)
        valid = self.legal_moves(pid)
        if valid and bot:
            next_pid = list(self.players)[self.next_index()]
            threat = len(self.hands[next_pid]) <= 2
            def score(i):
                c = self.hands[pid][i]
                # Avoid an illegal +4 when a legal alternative exists; prefer spending actions before finishing.
                legal_four = c['v'] != '+4' or not any(x['c'] == self.color for x in self.hands[pid])
                return (legal_four, c['c'] != 'black', len(self.hands[pid]) <= 3 and not c['v'].isdigit(), threat and c['v'] in ('+2', 'skip', 'reverse'), colors[c['c']])
            index = max(valid, key=score)
            if len(self.hands[pid]) == 2 and pid not in self.uno_ready:
                return self.declare_uno(pid)
            return self.play(pid, index, chosen)
        if self.pending_penalty:
            return self.settle_penalty(pid)
        if self.pending_draw:
            return self.pass_turn(pid)
        return self.take_card(pid, automatic=True)

    def state(self, pid):
        return {'type': 'state', 'you': pid, 'host': self.host, 'botCount': self.bot_count,
                'rules': {'stackDrawTwo': self.stack_draw_two, 'numberFinish': self.number_finish}, 'pendingPenalty': self.pending_penalty,
                'legalMoves': self.legal_moves(pid), 'drawnIndex': self.drawn_index if pid == self.current else None,
                'unoReady': pid in self.uno_ready, 'unoAnnounced': pid in self.uno_announced, 'unoVulnerable': self.uno_vulnerable,
                'openingWild': self.opening_wild, 'dealer': self.dealer, 'roundPoints': self.round_points,
                'matchWinner': self.match_winner,
                'challenge': {'actor': self.challenge['actor'], 'target': self.challenge['target']} if self.challenge else None,
                'challengeResult': self.challenge_result if self.challenge_result and self.challenge_result['viewer'] == pid else None,
                'players': [{'id': p, 'name': v['name'], 'count': len(self.hands[p]), 'bot': v['bot'], 'score': self.scores.get(p, 0)} for p, v in self.players.items()],
                'hand': self.hands.get(pid, []), 'top': self.discard[-1] if self.discard else None,
                'color': self.color, 'direction': self.direction, 'turn': self.current,
                'started': self.started, 'winner': self.winner, 'canDraw': not self.pending_draw and not bool(self.opening_wild),
                'message': self.message, 'event': self.event}

    async def broadcast(self):
        for p in list(self.humans):
            try:
                await self.players[p]['ws'].send(json.dumps(self.state(p), ensure_ascii=False))
            except Exception:
                pass
        self.schedule()

    def schedule(self):
        current_task = asyncio.current_task()
        if self.automation_task and self.automation_task is not current_task:
            self.automation_task.cancel()
        self.automation_task = None
        if self.automation_needed():
            self.automation_task = asyncio.create_task(self.delayed_step(self.revision))

    def decision_delay(self):
        if not self.current or not self.players[self.current]['bot']:
            return 1.15
        delay = random.uniform(2.0, 3.6)
        hand = self.hands[self.current]
        valid = [c for c in hand if self.playable(c)]
        if self.pending_penalty or any(c['c'] == 'black' for c in valid):
            delay += random.uniform(.4, .9)
        if any(len(h) <= 2 for h in self.hands.values()):
            delay += random.uniform(.2, .6)
        return min(delay, 5.1)

    async def delayed_step(self, revision):
        await asyncio.sleep(self.decision_delay())
        if self.revision == revision and self.auto_step():
            await self.broadcast()


game = Game()


async def handler(ws):
    pid = None
    try:
        async for raw in ws:
            try:
                m = json.loads(raw)
                if not isinstance(m, dict):
                    continue
                act = m.get('type')
                if act == 'join' and not pid:
                    pid = game.add_human(m.get('name', '玩家'), ws)
                elif pid:
                    if act == 'configure':
                        game.configure(pid, m.get('bots'))
                    elif act == 'rules':
                        game.set_rules(pid, m.get('stackDrawTwo'))
                    elif act == 'seats':
                        game.reorder(pid, m.get('order'))
                    elif act == 'shuffleSeats':
                        game.shuffle_seats(pid)
                    elif act == 'start':
                        game.start(pid)
                    elif act == 'uno':
                        if not game.declare_uno(pid):
                            continue
                    elif act == 'catchUno':
                        if not game.catch_uno(pid):
                            continue
                    elif act == 'challenge':
                        if not game.resolve_challenge(pid, True):
                            continue
                    elif act == 'openingColor':
                        if not game.choose_opening(pid, m.get('color')):
                            continue
                    elif act == 'play':
                        if not game.play(pid, m.get('index'), m.get('color'), m.get('uno', False)):
                            continue
                    elif act == 'draw':
                        if not game.take_card(pid):
                            continue
                    elif act == 'pass':
                        if not game.pass_turn(pid):
                            continue
                    else:
                        continue
                else:
                    continue
                await game.broadcast()
            except (ValueError, TypeError) as exc:
                await ws.send(json.dumps({'type': 'error', 'message': str(exc)}, ensure_ascii=False))
    finally:
        if pid:
            game.remove_human(pid)
            await game.broadcast()


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def log_message(self, *args):
        pass

    def end_headers(self):
        self.send_header('Cache-Control', 'no-cache')
        super().end_headers()


async def main():
    http = ThreadingHTTPServer((os.environ.get('GAME_BIND','127.0.0.1'), int(os.environ.get('ARCADE_HTTP_PORT','8765'))), Handler)
    Thread(target=http.serve_forever, daemon=True).start()
    print('UNO 已启动，支持 0–3 个人机：')
    try:
        ips = sorted({x[4][0] for x in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET) if not x[4][0].startswith('127.')})
    except OSError:
        ips = []
    for ip in ips:
        print(f'  http://{ip}:8765')
    async with serve(handler, os.environ.get('GAME_BIND','127.0.0.1'), int(os.environ.get('ARCADE_WS_PORT','8766')), max_size=4096):
        await asyncio.Future()


if __name__ == '__main__':
    asyncio.run(main())
