"""Portable game launcher. Ctrl+C stops only processes started by this launcher."""
import argparse
import json
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent

def listening(port):
    with socket.socket() as s:
        return s.connect_ex(('127.0.0.1', port)) == 0

def lan_address():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(('192.0.2.1', 80))
            return s.getsockname()[0]
    except OSError:
        return '127.0.0.1'

def run():
    parser = argparse.ArgumentParser(description='Tonight Club: 17 LAN browser games')
    parser.add_argument('--port', type=int, default=os.environ.get('PORT', '8780'), help='Main port (defaults to PORT or 8780); reserves this port and the next 9')
    parser.add_argument('--bind', default='0.0.0.0', help='Gateway address; use 127.0.0.1 for local-only')
    args = parser.parse_args()
    if not 1024 <= args.port <= 65526:
        parser.error('--port must be between 1024 and 65526')
    try:
        import websockets
    except ImportError:
        parser.error('Install Python dependencies first: python -m pip install -r requirements.txt')
    node = shutil.which('node')
    if not node:
        parser.error('Node.js 22+ is required for Starport Crew')
    if int(subprocess.check_output([node, '--version'], text=True).lstrip('v').split('.')[0]) < 22:
        parser.error('Node.js 22+ is required')
    if not (ROOT/'apps/starport/node_modules/ws/package.json').is_file():
        parser.error('Install Node dependencies first: npm --prefix apps/starport ci')
    occupied = [p for p in range(args.port, args.port+10) if listening(p)]
    if occupied:
        parser.error(f'Ports already in use: {occupied}. Try --port 18780; no existing process was changed.')
    data = ROOT/'.data'
    data.mkdir(exist_ok=True)
    services = [('arcade', 'main', args.port+1, args.port+2),
                ('extra', 'extra', args.port+3, args.port+4),
                ('uno', 'uno', args.port+5, args.port+6),
                ('cards', 'cards', args.port+7, args.port+8)]
    children, logs = [], []
    env = dict(os.environ, GAME_BIND='127.0.0.1', CLUB_GATEWAY_PORT=str(args.port), CLUB_GATEWAY_BIND=args.bind)
    for name, folder, http, ws in services:
        env[f'CLUB_{name.upper()}_HTTP'] = str(http)
        env[f'CLUB_{name.upper()}_WS'] = str(ws)
    env['CLUB_STARPORT_WS'] = str(args.port+9)
    def spawn(name, command, service_env):
        log = (data/f'{name}.log').open('a', encoding='utf-8')
        logs.append(log)
        p = subprocess.Popen(command, cwd=ROOT, env=service_env, stdout=log, stderr=log)
        children.append(p)
        return p
    def ready(p, ports, name):
        for _ in range(100):
            if p.poll() is not None:
                raise RuntimeError(f'{name} stopped; inspect .data/{name}.log')
            if all(listening(port) for port in ports):
                return
            time.sleep(.05)
        raise RuntimeError(f'{name} did not become ready; inspect .data/{name}.log')
    def stop_on_signal(signum, frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, stop_on_signal)
    try:
        for name, folder, http, ws in services:
            local = dict(env, ARCADE_HTTP_PORT=str(http), ARCADE_WS_PORT=str(ws))
            p = spawn(name, [sys.executable, '-u', str(ROOT/'apps'/folder/'server.py')], local)
            ready(p, (http, ws), name)
        p = spawn('starport', [node, str(ROOT/'apps/starport/server.mjs')],
                  dict(env, PORT=str(args.port+9), PROGRESS_FILE=str(data/'starport-progress.json')))
        ready(p, (args.port+9,), 'starport')
        p = spawn('gateway', [sys.executable, '-u', str(ROOT/'gateway.py')], env)
        ready(p, (args.port,), 'gateway')
        print(f'Local: http://127.0.0.1:{args.port}/', flush=True)
        if args.bind != '127.0.0.1':
            print(f'Same Wi-Fi: http://{lan_address()}:{args.port}/', flush=True)
        print('17 games ready. Keep this terminal open. Ctrl+C stops this instance.', flush=True)
        while True:
            if any(p.poll() is not None for p in children):
                raise RuntimeError('A service stopped; inspect .data/*.log')
            time.sleep(.5)
    except KeyboardInterrupt:
        pass
    finally:
        for p in reversed(children):
            if p.poll() is None:
                p.terminate()
        for p in children:
            try:
                p.wait(timeout=3)
            except subprocess.TimeoutExpired:
                p.kill()
                p.wait()
        for log in logs:
            log.close()

if __name__ == '__main__':
    run()
