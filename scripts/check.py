"""Run each game's rules in isolation, then test the complete LAN stack."""
from pathlib import Path
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
for app in ('main','extra','cards','uno'):
    subprocess.run([sys.executable,'-m','unittest','discover','-p','test_games.py'],cwd=ROOT/'apps'/app,check=True)
subprocess.run([shutil.which('npm') or 'npm','test'],cwd=ROOT/'apps/starport',check=True)
subprocess.run([sys.executable,str(ROOT/'tests/test_stack.py')],cwd=ROOT,check=True)
