"""Start Tonight Club on one port: all 17 games, invite links and the Starport sidecar.

Ctrl+C (or SIGTERM in the cloud) stops everything this launcher started.
"""
import argparse
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys

ROOT = Path(__file__).resolve().parent


def lan_address():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(('192.0.2.1', 80))
            return s.getsockname()[0]
    except OSError:
        return '127.0.0.1'


def main():
    parser = argparse.ArgumentParser(description='Tonight Club: 17 browser games for friends')
    parser.add_argument('--port', type=int, default=int(os.environ.get('PORT', '8780')), help='Public port (defaults to PORT or 8780)')
    parser.add_argument('--bind', default='0.0.0.0', help='Listen address; use 127.0.0.1 for this computer only')
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error('--port must be between 1 and 65535')
    try:
        import aiohttp  # noqa: F401
    except ImportError:
        parser.error('Install Python dependencies first: python -m pip install -r requirements.txt')
    node = shutil.which('node')
    if not node:
        parser.error('Node.js 22+ is required for Starport Crew')
    if int(subprocess.check_output([node, '--version'], text=True).lstrip('v').split('.')[0]) < 22:
        parser.error('Node.js 22+ is required')
    if not (ROOT / 'starport/node_modules/ws/package.json').is_file():
        parser.error('Install Node dependencies first: npm --prefix starport ci')
    with socket.socket() as s:
        if s.connect_ex(('127.0.0.1', args.port)) == 0:
            parser.error(f'Port {args.port} is already in use. Try --port 18780; no existing process was changed.')

    from server.app import run

    def ready():
        print(f'Local: http://127.0.0.1:{args.port}/', flush=True)
        if args.bind not in ('127.0.0.1', 'localhost'):
            print(f'Same Wi-Fi: http://{lan_address()}:{args.port}/', flush=True)
        print('17 games ready. Ctrl+C stops this instance.', flush=True)

    run(args.bind, args.port, ready)


if __name__ == '__main__':
    sys.path.insert(0, str(ROOT))
    main()
