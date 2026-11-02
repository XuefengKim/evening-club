"""Isolated end-to-end checks against the exported launcher and gateway."""
import asyncio
import json
import os
from pathlib import Path
import secrets
import signal
import socket
import subprocess
import sys
import time
from urllib.error import HTTPError
from urllib.request import urlopen
from websockets.asyncio.client import connect

ROOT = Path(__file__).resolve().parents[1]

def choose_port():
    for port in range(23780, 24780, 10):
        sockets=[]
        try:
            for p in range(port, port+10):
                s=socket.socket();s.bind(('127.0.0.1',p));sockets.append(s)
            return port
        except OSError:
            pass
        finally:
            for s in sockets:s.close()
    raise RuntimeError('No free test port block')

async def receive(ws, predicate=lambda m:m.get('type')=='state'):
    while True:
        m=json.loads(await asyncio.wait_for(ws.recv(),5))
        if m.get('type')=='error':raise AssertionError(m.get('message'))
        if predicate(m):return m

async def send(ws, **m):
    await ws.send(json.dumps(m))

async def tables(base, route, kinds):
    for kind in kinds:
        async with connect(base+route,proxy=None) as a, connect(base+route,proxy=None) as b:
            await send(a,type='create',game=kind,token=secrets.token_hex(16),name='Player A')
            await receive(a)
            await send(b,type='joinCurrent',token=secrets.token_hex(16),name='Player B')
            await receive(a,lambda m:m.get('type')=='state' and len(m['players'])==2)
            await receive(b)
            await send(a,type='start')
            x=await receive(a,lambda m:m.get('type')=='state' and m.get('game') is not None)
            y=await receive(b,lambda m:m.get('type')=='state' and m.get('game') is not None)
            assert x['kind']==y['kind']==kind
            assert x['game']['move']==y['game']['move']
            await send(a,type='leave');await receive(a,lambda m:m.get('type')=='left')
            await send(b,type='leave');await receive(b,lambda m:m.get('type')=='left')
        print('PASS two-client gateway table:',kind)

async def protocols(port):
    base=f'ws://127.0.0.1:{port}'
    await tables(base,'/ws/arcade',['connect','memory','dice','rps','number','boxes'])
    await tables(base,'/ws/extra',['tic','gomoku','reversi','nim','hex','code'])
    await tables(base,'/ws/cards',['eights','palace','golf'])
    async with connect(base+'/ws/uno',proxy=None) as a, connect(base+'/ws/uno',proxy=None) as b:
        await send(a,type='join',name='Player A');await receive(a)
        await send(b,type='join',name='Player B');await receive(b)
        await send(a,type='configure',bots=0)
        await send(a,type='start')
        await receive(a,lambda m:m.get('type')=='state' and m.get('started'))
        await receive(b,lambda m:m.get('type')=='state' and m.get('started'))
    print('PASS two-client UNO through gateway')
    async with connect(base+'/ws/starport',proxy=None) as a, connect(base+'/ws/starport',proxy=None) as b:
        await send(a,type='join');x=await receive(a,lambda m:m.get('type')=='joined')
        await send(b,type='join');y=await receive(b,lambda m:m.get('type')=='joined')
        assert (x['role'],y['role'])==(0,1)
        await send(a,type='start')
        await receive(a,lambda m:m.get('type')=='state' and m.get('started') and not m['paused'])
        await send(a,type='input',right=True)
        await receive(b,lambda m:m.get('type')=='state' and m['game']['players'][0]['x']>70)
        await send(a,type='leave');await send(b,type='leave')
    print('PASS Starport independent movement through same-origin gateway')

def main():
    port=choose_port()
    p=subprocess.Popen([sys.executable,str(ROOT/'start.py'),'--port',str(port),'--bind','127.0.0.1'],cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
    try:
        for _ in range(160):
            if p.poll() is not None:raise AssertionError(p.stdout.read())
            try:
                with urlopen(f'http://127.0.0.1:{port}/_health',timeout=.2) as r:
                    if r.status==200:break
            except OSError:time.sleep(.05)
        else:raise AssertionError('Stack readiness timeout')
        for route in ['/','/extra/','/uno/','/cards/','/starport/','/api/table','/extra/api/table','/cards/api/table','/starport/client.mjs','/starport/view.mjs','/starport/manifest.webmanifest','/starport/icon-192.png']:
            with urlopen(f'http://127.0.0.1:{port}'+route) as r:assert r.status==200,route
        with urlopen(f'http://127.0.0.1:{port}/starport/manifest.webmanifest') as r:
            manifest=json.load(r);assert manifest['scope']=='./' and manifest['start_url'].startswith('./')
        for route in ['/start.py','/.env','/starport/server.mjs','/cards/server.py','/../requirements.txt']:
            try:urlopen(f'http://127.0.0.1:{port}'+route)
            except HTTPError as e:assert e.code==404
            else:raise AssertionError('Private path served:'+route)
        asyncio.run(protocols(port))
        print('PASS all 17 games reachable on one origin; runtime/source files hidden')
    finally:
        if p.poll() is None:
            p.send_signal(signal.SIGINT)
        try:p.wait(timeout=10)
        except subprocess.TimeoutExpired:p.kill();p.wait();raise
        if p.stdout:p.stdout.close()
    time.sleep(.2)
    for check in range(port,port+10):
        with socket.socket() as s:assert s.connect_ex(('127.0.0.1',check))!=0,f'Leaked child on {check}'
    print('PASS launcher cleans up only its own child processes')

if __name__=='__main__':main()
