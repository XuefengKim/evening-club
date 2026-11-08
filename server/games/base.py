"""Shared pieces of every two-seat match. All moves and hidden information stay on the server."""


def integer(v, low, high):
    if type(v) is not int or not low <= v <= high:
        raise ValueError('请使用当前界面上可选的操作')
    return v


class Match:
    """Subclasses own the rules; the room only relies on this small surface."""

    def emit(self, kind, actor=None, **extra):
        self.move += 1
        self.event = {'kind': kind, 'actor': actor, **extra}

    def finish(self, winner):
        self.done = True
        self.winner = winner

    def transition(self):
        """Timed, actor-less step (memory flip-back, rock-paper-scissors next round)."""
        return False
