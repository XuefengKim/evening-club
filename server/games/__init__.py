"""Game rule modules. MATCHES maps every two-seat game kind to its Match class."""
from . import arcade, board, cards

MATCHES = {kind: module.Match for module in (arcade, board, cards) for kind in module.KINDS}
