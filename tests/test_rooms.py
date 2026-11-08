"""Room lifecycle and abuse budgets that only matter on the public internet."""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server import registry as reg  # noqa: E402
from server.table import Room  # noqa: E402
from server.uno_table import UnoTable  # noqa: E402


class Peer:
    async def send(self, text): pass
    async def close(self, code=1000, reason=''): pass


class Lifecycle(unittest.TestCase):
    def test_abandoned_tables_go_quickly_played_tables_keep_their_link(self):
        r = Room('ABCD', 'connect')
        r.join('A', 'a' * 32, Peer())
        r.players[0]['ws'] = None
        start = r.updated
        self.assertFalse(r.settled)
        self.assertFalse(reg.registry.expired(r, start + reg.ABANDONED_SECONDS - 1))
        self.assertTrue(reg.registry.expired(r, start + reg.ABANDONED_SECONDS + 1))
        r.join('B', 'b' * 32, Peer())
        self.assertTrue(r.settled)
        r.players[1]['ws'] = None
        self.assertFalse(reg.registry.expired(r, start + reg.ABANDONED_SECONDS + 1))
        self.assertTrue(reg.registry.expired(r, start + reg.IDLE_SECONDS + 1))

    def test_bot_practice_round_counts_as_played(self):
        r = Room('ABCE', 'tic')
        r.join('A', 'a' * 32, Peer())
        r.configure(0, {'type': 'bot', 'enabled': True})
        self.assertFalse(r.settled)
        r.start(0)
        self.assertTrue(r.settled)

    def test_connected_table_never_expires(self):
        r = Room('ABCF', 'connect')
        r.join('A', 'a' * 32, Peer())
        self.assertFalse(reg.registry.expired(r, r.updated + reg.IDLE_SECONDS * 10))

    def test_uno_table_settles_with_two_people(self):
        t = UnoTable('UNOA')
        t.add_human('A', Peer())
        self.assertFalse(t.settled)
        t.add_human('B', Peer())
        self.assertTrue(t.settled)


class Budgets(unittest.TestCase):
    def test_limiter_window(self):
        limiter = reg.Limiter(3, 60)
        with mock.patch.object(reg.time, 'monotonic', return_value=1000):
            self.assertTrue(all(limiter.allow('ip') for _ in range(3)))
            self.assertFalse(limiter.allow('ip'))
            self.assertTrue(limiter.allow('other'))
        with mock.patch.object(reg.time, 'monotonic', return_value=1061):
            self.assertTrue(limiter.allow('ip'))
            limiter.prune()
            self.assertNotIn('other', limiter.hits)

    def test_client_address_trusts_only_configured_proxy_hops(self):
        request = SimpleNamespace(remote='10.0.0.9', headers={'X-Forwarded-For': '6.6.6.6, 1.2.3.4'})
        with mock.patch.object(reg, 'PROXY_HOPS', 0):
            self.assertEqual(reg.client_address(request), '10.0.0.9')
        with mock.patch.object(reg, 'PROXY_HOPS', 1):
            self.assertEqual(reg.client_address(request), '1.2.3.4')  # a client-supplied first entry is ignored
        request.headers = {}
        with mock.patch.object(reg, 'PROXY_HOPS', 1):
            self.assertEqual(reg.client_address(request), '10.0.0.9')
        request.headers = {'CF-Connecting-IP': '9.9.9.9', 'X-Forwarded-For': '6.6.6.6, 1.2.3.4'}
        with mock.patch.object(reg, 'CLIENT_IP_HEADER', 'CF-Connecting-IP'), mock.patch.object(reg, 'PROXY_HOPS', 1):
            self.assertEqual(reg.client_address(request), '9.9.9.9')


if __name__ == '__main__':
    unittest.main()
