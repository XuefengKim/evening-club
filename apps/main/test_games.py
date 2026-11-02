import asyncio,importlib.util,random,unittest
from pathlib import Path
from collections import Counter
spec=importlib.util.spec_from_file_location('arcade',Path(__file__).with_name('server.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class WS:
 async def send(self,raw):pass
class Tests(unittest.IsolatedAsyncioTestCase):
 def room(self):
  r=m.Room('TEST','memory');r.join('A','a'*20,WS());r.join('B','b'*20,WS());return r
 async def complete(self,r):
  g=r.match
  for step in range(2000):
   if g.done:break
   if g.transition():continue
   g.action(g.turn,g.bot(g.turn))
  self.assertTrue(g.done);await r.publish()
 async def test_progression_and_cap(self):
  r=self.room()
  for expected in [1,2,3,4,4,4]:
   self.assertEqual(r.state(0)['progression']['nextMemoryLevel'],expected);r.start(0);self.assertEqual(r.match.level,expected);await self.complete(r)
   before=r.memory_progress;await r.publish();self.assertEqual(r.memory_progress,before)
  self.assertEqual(r.completed['memory'],6)
 async def test_fixed_difficulty_does_not_advance_ladder(self):
  r=self.room();r.configure(0,{'type':'difficulty','mode':'4'});r.start(0);await self.complete(r);self.assertEqual(r.memory_progress,0);self.assertEqual(r.next_memory_level(),4)
  r.configure(0,{'type':'difficulty','mode':'progressive'});self.assertEqual(r.next_memory_level(),1)
 async def test_permissions_bounds_and_reset(self):
  r=self.room()
  for mode in [0,True,'0','5','oops',None]:
   with self.assertRaises(ValueError):r.configure(0,{'type':'difficulty','mode':mode})
  with self.assertRaises(ValueError):r.configure(1,{'type':'difficulty','mode':'4'})
  r.start(0)
  for msg in [{'type':'difficulty','mode':'4'},{'type':'resetProgress'}]:
   with self.assertRaises(ValueError):r.configure(0,msg)
  await self.complete(r);self.assertEqual(r.next_memory_level(),2);r.configure(0,{'type':'resetProgress'});self.assertEqual(r.next_memory_level(),1)
 async def test_other_games_do_not_advance_and_switch_retains(self):
  r=self.room();r.start(0);await self.complete(r);r.configure(0,{'type':'game','game':'connect'});r.start(0);r.match.finish(0);await r.publish();self.assertEqual(r.next_memory_level(),2);r.configure(0,{'type':'game','game':'memory'});r.start(0);self.assertEqual(r.match.level,2)
 async def test_aborted_round_no_progress(self):
  r=self.room();r.start(0);r.match=None;self.assertEqual(r.next_memory_level(),1)
 async def test_all_levels_decks_privacy_bot_bounds(self):
  total=0
  for level,(pairs,columns,_) in m.MEMORY_LEVELS.items():
   for seed in range(30):
    random.seed(seed);g=m.Match('memory',level=level);self.assertEqual(len(g.cards),pairs*2);self.assertEqual(Counter(g.cards),Counter({i:2 for i in range(pairs)}));self.assertEqual(g.public(0)['cards'],[None]*(pairs*2));self.assertEqual(g.columns,columns)
    with self.assertRaises(ValueError):g.action(g.turn,{'act':'flip','index':pairs*2})
    for step in range(2000):
     if g.done:break
     if g.transition():continue
     actor=g.turn;move=g.bot(actor);self.assertTrue(0<=move['index']<pairs*2);g.action(actor,move);pub=g.public(1-actor)
     for i,v in enumerate(pub['cards']):
      if i not in g.open and g.matched[i]==-1:self.assertIsNone(v)
     self.assertEqual(sum(g.scores)*2,sum(v!=-1 for v in g.matched))
    self.assertTrue(g.done);self.assertEqual(sum(g.scores),pairs);total+=1
  print('PASS',total,'full memory matches across 4 levels, private cards and every-step scoring')
if __name__=='__main__':unittest.main()
