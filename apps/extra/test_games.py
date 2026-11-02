import copy
import random
import unittest
import server

class Rules(unittest.TestCase):
    def test_tic_win_draw_validation(self):
        g=server.Match('tic',0)
        for r,c in [(0,0),(1,0),(0,1),(1,1),(0,2)]:g.action(g.turn,dict(act='place',row=r,col=c))
        self.assertEqual(g.winner,0)
        g=server.Match('tic',0)
        for r,c in [(0,0),(0,1),(0,2),(1,1),(1,0),(1,2),(2,1),(2,0),(2,2)]:g.action(g.turn,dict(act='place',row=r,col=c))
        self.assertTrue(g.done);self.assertEqual(g.winner,-1)
        g=server.Match('tic',0)
        before=copy.deepcopy(g.__dict__)
        for actor,msg in [(1,dict(act='place',row=0,col=0)),(0,dict(act='place',row=-1,col=0)),(0,dict(act='place',row=True,col=0))]:
            with self.assertRaises(ValueError):g.action(actor,msg)
            self.assertEqual(before,g.__dict__)

    def test_gomoku_all_directions_and_six(self):
        for dr,dc in [(0,1),(1,0),(1,1),(1,-1)]:
            g=server.Match('gomoku',0)
            for i in range(4):g.board[5+dr*i][5+dc*i]=0
            g.action(0,dict(act='place',row=5+dr*4,col=5+dc*4));self.assertEqual(g.winner,0)
        g=server.Match('gomoku',0)
        for c in [0,1,2,4,5]:g.board[0][c]=0
        g.action(0,dict(act='place',row=0,col=3));self.assertEqual(g.winner,0)

    def test_reversi_flip_skip_end(self):
        g=server.Match('reversi',0)
        self.assertEqual(len(g.legal(0)),4)
        r,c=g.legal(0)[0];g.action(0,dict(act='place',row=r,col=c));self.assertEqual(g.scores,[4,1])
        g=server.Match('reversi',0)
        g.board=[[0]*6 for _ in range(6)]
        g.board[0][0]=-1;g.board[0][1]=1;g.board[5][5]=-1;g.board[5][4]=1
        g.action(0,dict(act='place',row=0,col=0));self.assertEqual(g.turn,0);self.assertFalse(g.done)
        g.action(0,dict(act='place',row=5,col=5));self.assertTrue(g.done);self.assertEqual(g.winner,0);self.assertEqual(g.scores,[36,0])

    def test_hex_paths(self):
        for actor in [0,1]:
            g=server.Match('hex',actor)
            for i in range(4):g.board[i if actor==0 else 2][2 if actor==0 else i]=actor
            g.action(actor,dict(act='place',row=4 if actor==0 else 2,col=2 if actor==0 else 4))
            self.assertEqual(g.winner,actor)
        g=server.Match('hex',0)
        for i in range(5):g.board[i][4-i]=0
        self.assertTrue(g.hex_path(0))

    def test_nim_last_wins_and_limits(self):
        g=server.Match('nim',0);g.piles=[0,0,2]
        with self.assertRaises(ValueError):g.action(0,dict(act='take',pile=0,count=1))
        with self.assertRaises(ValueError):g.action(0,dict(act='take',pile=2,count=3))
        g.action(0,dict(act='take',pile=2,count=2));self.assertEqual(g.winner,0)

    def test_code_privacy_clues_and_bot(self):
        self.assertEqual(server.feedback('024','042'),(1,2))
        g=server.Match('code',0);g.secret='024'
        for bad in ['000','678',24,None]:
            with self.assertRaises(ValueError):g.action(0,dict(act='guess',guess=bad))
        self.assertIsNone(g.public(0)['secret'])
        g.action(0,dict(act='guess',guess='042'))
        with self.assertRaises(ValueError):g.action(1,dict(act='guess',guess='042'))
        public=g.public(1);g.secret='105';random.seed(42);a=g.bot(1)
        g.secret='531';random.seed(42);b=g.bot(1)
        self.assertEqual(a,b) # identical clues and RNG: bot never reads secret
        g.secret='024';g.action(1,dict(act='guess',guess='024'));self.assertEqual(g.winner,1)
        self.assertEqual(g.public(0)['secret'],'024')

    def test_random_complete_games(self):
        for kind in server.KINDS:
            for _ in range(12):
                g=server.Match(kind)
                for move in range(160):
                    if g.done:break
                    actor=g.turn
                    if kind=='tic':
                        r,c=random.choice(g.legal(actor));action=dict(act='place',row=r,col=c)
                    else:action=g.bot(actor)
                    before=copy.deepcopy(g.__dict__)
                    if kind!='tic':
                        g.bot(actor)
                        self.assertEqual(before,g.__dict__)
                    g.action(actor,action)
                self.assertTrue(g.done,(kind,g.move))
                self.assertIn(g.winner,[-1,0,1])
                if kind=='hex':self.assertNotEqual(g.winner,-1)

    def test_tic_bot_never_loses(self):
        for first in (0,1):
            for _ in range(4):
                g=server.Match('tic',first)
                while not g.done:
                    if g.turn==1:msg=g.bot(1)
                    else:
                        r,c=random.choice(g.legal(0));msg=dict(act='place',row=r,col=c)
                    g.action(g.turn,msg)
                self.assertIn(g.winner,[-1,1])

if __name__=='__main__':unittest.main()
