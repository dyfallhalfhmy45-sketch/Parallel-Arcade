"""Relay positions between a separately supplied local adapter and Parallel rooms.
Adapter HTTP contract: GET /player -> {x,y,z}; POST /peers -> {peer_id:{x,y,z}}.
Run python backend/sync_client.py --server wss://host --room my-room --adapter http://127.0.0.1:8765
"""
import argparse
import asyncio
import json
import os
import httpx
import websockets


async def run(args):
    token = os.environ.get('PARALLEL_TOKEN')
    if not token:
        raise SystemExit('Set PARALLEL_TOKEN first')
    async with websockets.connect(args.server.rstrip('/')+'/ws/'+args.room, max_size=65536) as ws, httpx.AsyncClient(base_url=args.adapter,timeout=2) as client:
        await ws.send(json.dumps({'type':'auth','token':token}))
        ready = json.loads(await ws.recv())
        if ready.get('type') != 'ready':
            raise RuntimeError('Room authentication failed')
        async def send():
            while True:
                response = await client.get('/player')
                response.raise_for_status()
                position = response.json()
                await ws.send(json.dumps({'type':'position',**{k:float(position.get(k,0)) for k in ('x','y','z')}}))
                await asyncio.sleep(.1)
        async def receive():
            async for raw in ws:
                data = json.loads(raw)
                if data.get('type') == 'positions':
                    response = await client.post('/peers',json=data['players'])
                    response.raise_for_status()
        sender, receiver = asyncio.create_task(send()), asyncio.create_task(receive())
        done, pending = await asyncio.wait([sender, receiver],return_when=asyncio.FIRST_COMPLETED)
        for task in pending:
            task.cancel()
        for task in done:
            task.result()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--server',required=True)
    parser.add_argument('--room',required=True)
    parser.add_argument('--adapter',default='http://127.0.0.1:8765')
    args = parser.parse_args()
    import re
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,40}',args.room):
        parser.error('Invalid room name')
    asyncio.run(run(args))
