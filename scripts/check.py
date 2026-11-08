"""Full local check: game rules, Starport engine and network, then the whole stack on an isolated port."""
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
RULES = ['tests.test_arcade', 'tests.test_board', 'tests.test_cards', 'tests.test_uno', 'tests.test_rooms']
subprocess.run([sys.executable, '-m', 'unittest', *RULES], cwd=ROOT, check=True)
subprocess.run([shutil.which('npm') or 'npm', 'test'], cwd=ROOT / 'starport', check=True)
subprocess.run([sys.executable, str(ROOT / 'tests/test_stack.py')], cwd=ROOT, check=True)
