import copy
import random
import unittest
import server as s

def card(r,suit=0):return suit*13+r-1
class CardRules(unittest.TestCase):
    def test_eights_wild_draw_skip_and_finish(self):
        g=s.Match('eights',0);g.pile=[card(7)];g.active_suit='spades';g.hands=[[card(8,1),card(12,2),card(2,2),card(9,2)],[card(3,1)]]
        before=copy.deepcopy(g.__dict__)
        with self.assertRaises(ValueError):g.action(0,dict(act='play',card=card(8,1),suit='bad'))
        self.assertEqual(before,g.__dict__)
        g.action(0,dict(act='play',card=card(8,1),suit='clubs'));self.assertEqual(g.active_suit,'clubs');self.assertEqual(g.turn,1)
        g.action(1,dict(act='draw'));g.action(0,dict(act='play',card=card(12,2)));self.assertEqual(g.turn,0)
        n=len(g.hands[1]);g.action(0,dict(act='play',card=card(2,2)));self.assertEqual(g.turn,0);self.assertEqual(len(g.hands[1]),n+2)
        g.action(0,dict(act='play',card=card(9,2)));self.assertEqual(g.winner,0)
        g=s.Match('eights',0);g.hands[0]=[card(2)];g.active_suit='spades';n=len(g.hands[1]);g.action(0,dict(act='play',card=card(2)));self.assertEqual(len(g.hands[1]),n)

    def test_eights_recycle_and_hidden(self):
        g=s.Match('eights',0);g.deck=[];g.pile=[0,1,2];g.hands=[[3],[4]];g.active_suit='spades'
        g.action(0,dict(act='draw'));self.assertEqual(g.pile,[2]);self.assertEqual(len(g.deck),1)
        pub=g.public(0);self.assertNotIn('hands',pub);self.assertEqual(pub['hand'],g.hands[0]);self.assertNotIn('deck',pub)

    def test_palace_preparation_and_burn(self):
        g=s.Match('palace',0);a=g.hands[0][0];b=g.up[0][1]
        g.action(0,dict(act='swap',hand=0,slot=1));self.assertEqual(g.hands[0][0],b);self.assertEqual(g.up[0][1],a)
        g.action(0,dict(act='ready'));g.action(1,dict(act='ready'));self.assertEqual(g.phase,'play')
        g.deck=[];g.hands[0]=[card(10),card(3)];g.pile=[card(1)]
        g.action(0,dict(act='play',cards=[card(10)]));self.assertEqual(g.turn,0);self.assertFalse(g.pile);self.assertTrue(g.burned)
        g.hands[0]=[card(7,3),card(3)];g.pile=[card(7),card(7,1),card(7,2)]
        g.action(0,dict(act='play',cards=[card(7,3)]));self.assertFalse(g.pile);self.assertEqual(g.turn,0)

    def test_palace_blind_failure_and_finish(self):
        g=s.Match('palace',0);g.phase='play';g.deck=[];g.hands[0]=[];g.up[0]=[None]*3;g.down[0]=[card(3),None,None];g.pile=[card(13)]
        g.action(0,dict(act='play',slot=0));self.assertEqual(g.hands[0],[card(13),card(3)]);self.assertFalse(g.done);self.assertEqual(g.turn,1)
        g.turn=0;g.hands[0]=[];g.down[0]=[card(2),None,None];g.pile=[card(13)]
        g.action(0,dict(act='play',slot=0));self.assertEqual(g.winner,0)
        g=s.Match('palace',0);pub=g.public(0);self.assertTrue(all(type(x)is bool for row in pub['down'] for x in row));self.assertNotIn('deck',pub)

    def test_golf_setup_final_turn_and_scores(self):
        g=s.Match('golf',0)
        for a,i in [(0,0),(0,1),(1,0),(1,1)]:g.action(a,dict(act='reveal',slot=i))
        self.assertEqual(g.phase,'play');self.assertEqual(g.turn,0)
        self.assertIsNone(g.public(0)['layouts'][0][2])
        g.faceup[0]=[True]*5+[False];g.action(0,dict(act='draw',source='deck'))
        self.assertIsNone(g.public(1)['pending']);self.assertNotIn('card',g.public(1)['event'])
        g.action(0,dict(act='replace',slot=5));self.assertEqual(g.closer,0);self.assertFalse(g.done)
        g.action(1,dict(act='draw',source='pile'))
        with self.assertRaises(ValueError):g.action(1,dict(act='discard',slot=2))
        g.action(1,dict(act='replace',slot=2));self.assertTrue(g.done);self.assertTrue(all(c is not None for row in g.public(0)['layouts'] for c in row))
        g.layouts[0]=[card(2),card(1),card(13),card(2,1),card(12),card(5)];self.assertEqual(g.golf_score(0),16)

    def test_bot_uses_only_client_information(self):
        for kind in s.KINDS:
            g=s.Match(kind,0);random.seed(8);a=g.bot(0)
            if kind=='golf':g.layouts[1]=list(reversed(g.layouts[1]))
            else:g.hands[1]=list(reversed(g.hands[1]))
            g.deck.reverse()
            if kind=='palace':g.down[0].reverse();g.down[1].reverse()
            random.seed(8);self.assertEqual(a,g.bot(0))

    def test_simulated_games_conserve_52_cards(self):
        for kind in s.KINDS:
            for seed in range(70):
                random.seed(seed);g=s.Match(kind)
                for move in range(1500):
                    cards=g.deck+g.pile+g.burned
                    if kind=='golf':cards+=sum(g.layouts,[])+([] if g.pending is None else [g.pending])
                    else:
                        cards+=sum(g.hands,[])
                        if kind=='palace':cards += [c for row in g.up+g.down for c in row if c is not None]
                    self.assertEqual(sorted(cards),list(range(52)),(kind,seed,move))
                    if g.done:break
                    before=copy.deepcopy(g.__dict__);actor=g.turn;msg=g.bot(actor);self.assertEqual(before,g.__dict__)
                    g.action(actor,msg)
                self.assertTrue(g.done,(kind,seed,g.move))
                self.assertIn(g.winner,[-1,0,1])

    def test_invalid_actions_are_atomic(self):
        for kind in s.KINDS:
            g=s.Match(kind,0);before=copy.deepcopy(g.__dict__)
            for msg in [dict(act='nonsense'),dict(act='play',card=True,cards=[True]),dict(act='reveal',slot=-1)]:
                with self.assertRaises(ValueError):g.action(0,msg)
                self.assertEqual(before,g.__dict__)
            with self.assertRaises(ValueError):g.action(1,g.bot(0))
            self.assertEqual(before,g.__dict__)

if __name__=='__main__':unittest.main()
