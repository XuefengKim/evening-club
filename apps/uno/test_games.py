import unittest,importlib.util,random
from pathlib import Path
from collections import Counter
spec=importlib.util.spec_from_file_location('uno',Path(__file__).with_name('server.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def c(color,v):return {'c':color,'v':v}
def room(n=3):
 g=m.Game();a=g.add_human('A',None)
 if n==5:g.add_human('B',None)
 g.configure(a,min(n-1,3));g.start(a);g.clear_choices();g.turn=0;g.direction=1;g.color='red';g.discard=[c('red','5')];g.deck=[c('yellow','7') for _ in range(40)];g.pending_draw=False;g.pending_penalty=0
 for p in g.players:g.hands[p]=[c('blue','1'),c('green','2')]
 return g,list(g.players)
class Rules(unittest.TestCase):
 def test_all_actions_cannot_finish(self):
  for value in ['skip','reverse','+2','wild','+4']:
   g,ids=room();a=ids[0];g.hands[a]=[c('black' if value in ['wild','+4'] else 'red',value)];self.assertEqual(g.legal_moves(a),[]);self.assertFalse(g.play(a,0,'red'));self.assertIsNone(g.winner);g.auto_step();self.assertEqual(len(g.hands[a]),2)
 def test_numeric_finish_scores(self):
  g,ids=room();a,b,d=ids;g.hands[a]=[c('red','9')];g.hands[b]=[c('green','7'),c('red','skip')];g.hands[d]=[c('black','wild'),c('black','+4')];g.play(a,0);self.assertEqual(g.winner,a);self.assertEqual(g.round_points,127);self.assertEqual(g.scores[a],127)
 def test_only_drawn_card(self):
  g,ids=room();a=ids[0];g.hands[a]=[c('red','1'),c('red','2')];g.deck=[c('red','3')];g.take_card(a);self.assertEqual(g.legal_moves(a),[2]);self.assertFalse(g.play(a,0));self.assertTrue(g.play(a,2));self.assertIsNone(g.drawn_index)
 def test_drawn_unplayable_auto_pass(self):
  g,ids=room();a=ids[0];g.hands[a]=[c('red','1'),c('blue','2')];g.take_card(a);self.assertEqual(g.legal_moves(a),[]);g.auto_step();self.assertEqual(g.current,ids[1]);self.assertFalse(g.pending_draw)
 def test_last_function_cannot_stack(self):
  g,ids=room();a,b,d=ids;g.stack_draw_two=True;g.hands[a]=[c('red','+2'),c('blue','1')];g.hands[b]=[c('green','+2')];g.declare_uno(a);g.play(a,0);self.assertEqual(g.legal_moves(b),[]);g.auto_step();self.assertEqual(len(g.hands[b]),3);self.assertEqual(g.current,d)
 def four(self,illegal):
  g,ids=room();a,b,d=ids;g.hands[a]=[c('black','+4'),c('red' if illegal else 'green','2')];g.play(a,0,'blue');return g,ids
 def test_challenge_success_private_evidence(self):
  g,ids=self.four(True);a,b,d=ids;self.assertEqual(g.current,b);self.assertIsNone(g.state(b)['challengeResult']);self.assertNotIn('illegal',g.state(b)['challenge']);self.assertEqual(g.legal_moves(b),[]);self.assertFalse(g.pass_turn(b,True));self.assertFalse(g.play(b,0));self.assertTrue(g.resolve_challenge(b,True));self.assertEqual(len(g.hands[a]),5);self.assertEqual(g.current,b);self.assertIsNotNone(g.state(b)['challengeResult']);self.assertIsNone(g.state(a)['challengeResult']);self.assertIsNone(g.state(d)['challengeResult']);self.assertEqual(g.state(b)['challengeResult']['color'],'red')
 def test_challenge_failure_and_accept(self):
  for challenge,amount in [(True,6),(False,4)]:
   g,ids=self.four(False);a,b,d=ids;old=len(g.hands[b]);g.resolve_challenge(b,challenge);self.assertEqual(len(g.hands[b]),old+amount);self.assertEqual(g.current,d);self.assertIsNone(g.challenge)
 def test_uno_ready_and_catch(self):
  g,ids=room();a,b,d=ids;g.hands[a]=[c('red','1'),c('blue','2')];self.assertTrue(g.declare_uno(a));g.play(a,0);self.assertIsNone(g.uno_vulnerable);self.assertFalse(g.catch_uno(b))
  g,ids=room();a,b,d=ids;g.hands[a]=[c('red','1'),c('blue','2')];g.play(a,0);self.assertEqual(g.uno_vulnerable,a);self.assertFalse(g.catch_uno(a));self.assertTrue(g.catch_uno(d));self.assertEqual(len(g.hands[a]),3);self.assertEqual(g.current,b);self.assertFalse(g.catch_uno(b))
 def test_uno_recover_and_expire(self):
  for recover in [True,False]:
   g,ids=room();a,b,d=ids;g.hands[a]=[c('red','1'),c('blue','2')];g.play(a,0)
   if recover:self.assertTrue(g.declare_uno(a))
   else:g.take_card(b)
   self.assertIsNone(g.uno_vulnerable);self.assertFalse(g.catch_uno(d))
 def test_uno_after_draw(self):
  g,ids=room();a=ids[0];g.hands[a]=[c('red','reverse')];g.deck=[c('red','9')];g.take_card(a);g.declare_uno(a);self.assertTrue(g.play(a,1));self.assertIsNone(g.uno_vulnerable);self.assertIsNone(g.winner)
 def test_initial_cards(self):
  original=m.freshdeck
  try:
   for value in ['wild','skip','reverse','+2','+4','8']:
    for stack in [True,False]:
     g=m.Game();a=g.add_human('A',None);g.configure(a,2);g.stack_draw_two=stack
     cards=[c('blue','3') for _ in range(108)];cards[-22]=c('black' if value in ['wild','+4'] else 'red',value);m.freshdeck=lambda:[dict(c) for c in cards];g.start(a)
     self.assertNotEqual(g.discard[-1]['v'],'+4');self.assertEqual(sum(map(len,g.hands.values())),23 if value=='+2' and not stack else 21)
     if value=='wild':self.assertEqual(g.opening_wild,g.current);self.assertFalse(g.play(g.current,0));self.assertTrue(g.choose_opening(g.current,'green'));self.assertEqual(g.color,'green')
     if value=='reverse':self.assertEqual(g.current,g.dealer);self.assertEqual(g.direction,-1)
     if value=='+2' and stack:self.assertEqual(g.pending_penalty,2)
  finally:m.freshdeck=original
 def test_dealer_and_500(self):
  g,ids=room();a=ids[0];old=g.dealer;g.scores[a]=499;g.hands[a]=[c('red','1')];g.play(a,0);self.assertEqual(g.match_winner,a);g.start(a);self.assertTrue(all(v==0 for v in g.scores.values()));self.assertEqual(g.dealer,ids[(ids.index(old)+1)%len(ids)]);self.assertIsNone(g.match_winner)
 def test_score_preserved_and_roster_reset(self):
  g,ids=room();a=ids[0];g.hands[a]=[c('red','1')];g.play(a,0);points=g.scores[a];g.start(a);self.assertEqual(g.scores[a],points);g.started=False;g.configure(a,1);self.assertTrue(all(v==0 for v in g.scores.values()))
 def test_simulations(self):
  for stack in [False,True]:
   for n in [2,3,4,5]:
    for seed in range(30):
     random.seed(seed);g=m.Game();a=g.add_human('A',None)
     if n==5:g.add_human('B',None)
     g.configure(a,min(n-1,3));g.stack_draw_two=stack;g.shuffle_seats(a);g.start(a)
     for p in g.players:g.players[p]['bot']=True
     original=Counter((c['c'],c['v']) for hand in g.hands.values() for c in hand)+Counter((c['c'],c['v']) for c in g.deck+g.discard);self.assertEqual(sum(original.values()),108)
     for step in range(3000):
      if g.winner or not g.started:break
      self.assertTrue(g.auto_step());now=Counter((c['c'],c['v']) for hand in g.hands.values() for c in hand)+Counter((c['c'],c['v']) for c in g.deck+g.discard);self.assertEqual(now,original)
     self.assertTrue(g.winner or not g.started,f'stalled stack={stack},n={n},seed={seed}')
     if g.winner:self.assertTrue(g.discard[-1]['v'].isdigit())
  print('PASS 240 complete-rule games: classic/stack, 2–5 seats, 108-card conservation, all winners finish on numbers')
if __name__=='__main__':unittest.main()
