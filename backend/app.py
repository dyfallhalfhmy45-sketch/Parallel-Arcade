"""Single-user self-hosted gateway. See README before exposing it publicly."""
import asyncio
import contextlib
import hmac
import io
import json
import math
import os
import re
import time
import uuid
from collections import OrderedDict
from pathlib import Path

import httpx
from fastapi import FastAPI, Depends, Header, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(os.getenv('DATA_DIR', str(ROOT / 'data')))
DATA.mkdir(parents=True, exist_ok=True)
TOKEN = os.getenv('PARALLEL_TOKEN', '')
ORIGINS = [s.strip() for s in os.getenv('ALLOWED_ORIGINS', 'http://localhost:8000,http://127.0.0.1:8000').split(',') if s.strip()]
MAX_ISO = int(os.getenv('MAX_ISO_BYTES', str(8 * 1024**3)))
app = FastAPI(title='Parallel Arcade Gateway', version='0.1.0', docs_url=None, redoc_url=None)
app.add_middleware(CORSMiddleware, allow_origins=ORIGINS, allow_methods=['GET','POST'], allow_headers=['Authorization','Content-Type'])
Image.MAX_IMAGE_PIXELS = 16000000
translation_lock = asyncio.Lock()
cache = OrderedDict()
rooms = {}
peers = set()


def authorized(token):
    return bool(TOKEN and len(TOKEN) >= 24 and not TOKEN.startswith('replace-with-') and hmac.compare_digest(token, TOKEN))


async def auth(authorization: str = Header(default='')):
    if not TOKEN or len(TOKEN) < 24 or TOKEN.startswith('replace-with-'):
        raise HTTPException(503, 'Set PARALLEL_TOKEN to a random string of at least 24 characters on the server.')
    if not authorized(authorization.removeprefix('Bearer ')):
        raise HTTPException(401, 'Invalid access token')


def translator():
    try:
        import argostranslate.translate as tr
        langs = tr.get_installed_languages()
        english = next(x for x in langs if x.code == 'en')
        arabic = next(x for x in langs if x.code == 'ar')
        return english.get_translation(arabic)
    except Exception as exc:
        raise RuntimeError('Arabic model unavailable. Run: python backend/install_model.py') from exc


async def translate(text):
    text = text.strip()[:3000]
    if not text:
        return ''
    async with translation_lock:
        if text in cache:
            cache.move_to_end(text)
            return cache[text]
        try:
            result = await asyncio.to_thread(lambda: translator().translate(text))
        except Exception as exc:
            raise HTTPException(503, str(exc)) from exc
        cache[text] = result
        if len(cache) > 256:
            cache.popitem(last=False)
        return result


@app.get('/api/health', dependencies=[Depends(auth)])
async def health():
    try:
        await asyncio.to_thread(translator)
        ready = True
    except Exception:
        ready = False
    return {'status':'ok', 'translation_ready':ready, 'iso_launch':False, 'video_stream':bool(os.getenv('DISPLAY_SOURCE')), 'version':'0.1.0'}


class TextRequest(BaseModel):
    text: str = Field(min_length=1, max_length=3000)


@app.post('/api/translate', dependencies=[Depends(auth)])
async def translate_endpoint(payload: TextRequest):
    return {'arabic':await translate(payload.text)}


def read_text(image):
    import pytesseract
    return pytesseract.image_to_string(image, lang='eng', config='--psm 11', timeout=15).strip()[:3000]


@app.post('/api/ocr', dependencies=[Depends(auth)])
async def ocr_endpoint(request: Request):
    # Bound the entire request before multipart parsing to prevent oversized images.
    chunks, size = [], 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > 6 * 1024**2:
            raise HTTPException(413, 'Screenshot limit is 5 MB')
        chunks.append(chunk)
    request._body = b''.join(chunks)
    form = await request.form(max_files=1, max_fields=0)
    file = form.get('file')
    if not file or not hasattr(file, 'read'):
        raise HTTPException(422, 'Image file required')
    try:
        raw = await file.read()
        if len(raw) > 5 * 1024**2:
            raise HTTPException(413, 'Screenshot limit is 5 MB')
        image = Image.open(io.BytesIO(raw))
        if image.width * image.height > 16000000:
            raise HTTPException(413, 'Image pixel limit exceeded')
        image = image.convert('RGB')
        english = await asyncio.to_thread(read_text, image)
        return {'english':english, 'arabic':await translate(english)}
    except (UnidentifiedImageError, Image.DecompressionBombError) as exc:
        raise HTTPException(422, 'Invalid or oversized image') from exc
    except RuntimeError as exc:
        raise HTTPException(503, 'OCR unavailable or timed out; check Tesseract installation') from exc
    finally:
        await file.close()


@app.post('/api/games', dependencies=[Depends(auth)])
async def upload_game(request: Request):
    # Multipart upload; a reverse proxy must also enforce the request body limit.
    length = request.headers.get('content-length')
    if length is None:
        raise HTTPException(411, 'Content-Length required')
    try:
        if int(length) > MAX_ISO + 1024 * 1024:
            raise HTTPException(413, 'ISO exceeds configured server limit')
    except ValueError as exc:
        raise HTTPException(400, 'Invalid Content-Length') from exc
    form = await request.form(max_files=1, max_fields=1)
    file = form.get('file')
    if not file or not hasattr(file, 'read') or not (file.filename or '').lower().endswith('.iso'):
        raise HTTPException(422, 'An ISO file is required')
    game_id = uuid.uuid4().hex
    target = DATA / (game_id + '.iso')
    try:
        raw = form.get('profile', '')
        if not isinstance(raw, str) or len(raw) > 100000:
            raise ValueError('Invalid profile size')
        profile = json.loads(raw)
        if profile.get('schema_version') != 1 or not all(isinstance(profile.get(k), str) and profile[k] for k in ('id','title','adapter','game_version')):
            raise ValueError('Profile requires schema_version=1, id, title, adapter, game_version')
        size = 0
        with target.open('wb') as out:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_ISO:
                    raise HTTPException(413, 'ISO exceeds server limit')
                out.write(chunk)
        if not size:
            raise ValueError('Empty ISO file')
        (DATA / (game_id + '.json')).write_text(json.dumps(profile, ensure_ascii=False), encoding='utf-8')
        return {'id':game_id, 'bytes':size, 'status':'stored', 'launch_supported':False}
    except (ValueError, json.JSONDecodeError) as exc:
        target.unlink(missing_ok=True)
        raise HTTPException(422, str(exc)) from exc
    except BaseException:
        target.unlink(missing_ok=True)
        raise
    finally:
        await file.close()


async def publish_positions(room):
    members = rooms.get(room, {})
    for client_id, member in list(members.items()):
        with contextlib.suppress(Exception):
            await member['ws'].send_json({'type':'positions','players':{i:m['position'] for i,m in members.items() if i != client_id and m['position'] is not None}})


async def emit_iot(event):
    # Admin-owned fixed destination. Browser clients cannot choose arbitrary URLs.
    url = os.getenv('IOT_WEBHOOK_URL')
    if url:
        with contextlib.suppress(httpx.HTTPError):
            async with httpx.AsyncClient(timeout=2, follow_redirects=False) as client:
                await client.post(url, json={'event':event,'color':'#b99bff','duration_ms':400}, headers={'Authorization':'Bearer '+os.getenv('IOT_WEBHOOK_TOKEN','')})


@app.websocket('/ws/{room}')
async def room_socket(ws: WebSocket, room: str):
    origin = ws.headers.get('origin')
    if (origin and origin not in ORIGINS) or not re.fullmatch(r'[A-Za-z0-9_-]{1,40}',room):
        await ws.close(code=1008)
        return
    await ws.accept()
    client_id = uuid.uuid4().hex[:12]
    try:
        message = await asyncio.wait_for(ws.receive_json(), timeout=8)
        if message.get('type') != 'auth' or not authorized(str(message.get('token',''))):
            await ws.close(code=1008)
            return
        if len(rooms) >= 100 and room not in rooms or len(rooms.get(room,{})) >= 8:
            await ws.close(code=1013)
            return
        rooms.setdefault(room,{})[client_id] = {'ws':ws,'position':None}
        await ws.send_json({'type':'ready','client_id':client_id})
        last_position, last_event = 0.0, 0.0
        while True:
            message = await ws.receive_json()
            now = time.monotonic()
            if message.get('type') == 'position' and now-last_position >= .07:
                values = [message.get(k,0) for k in ('x','y','z')]
                if not all(isinstance(v,(float,int)) and math.isfinite(v) and abs(v)<=1e6 for v in values):
                    continue
                last_position = now
                rooms[room][client_id]['position'] = dict(zip(('x','y','z'),values))
                await publish_positions(room)
            elif message.get('type') == 'event' and message.get('event') == 'energy' and now-last_event >= 1:
                last_event = now
                for member in list(rooms[room].values()):
                    with contextlib.suppress(Exception):
                        await member['ws'].send_json({'type':'event','event':'energy'})
                await emit_iot('energy')
    except (WebSocketDisconnect, asyncio.TimeoutError, ValueError, KeyError, TypeError):
        pass
    finally:
        if room in rooms:
            rooms[room].pop(client_id, None)
            if not rooms[room]:
                rooms.pop(room,None)
            else:
                await publish_positions(room)
        with contextlib.suppress(Exception):
            await ws.close()


def ice_servers():
    servers=[]
    if os.getenv('TURN_URL'):
        servers.append({'urls':[os.environ['TURN_URL']], 'username':os.getenv('TURN_USERNAME',''), 'credential':os.getenv('TURN_PASSWORD','')})
    return servers


@app.get('/api/rtc-config', dependencies=[Depends(auth)])
async def rtc_config():
    return {'iceServers':ice_servers()}


class Offer(BaseModel):
    sdp: str = Field(max_length=100000)
    type: str = Field(pattern='^offer$')


@app.post('/api/offer', dependencies=[Depends(auth)])
async def offer(payload: Offer):
    if not os.getenv('DISPLAY_SOURCE'):
        raise HTTPException(503, 'Configure DISPLAY_SOURCE (for example :99.0) on a Linux emulator host. See README.')
    if len(peers) >= 4:
        raise HTTPException(429, 'Maximum concurrent video streams reached')
    try:
        from aiortc import RTCPeerConnection, RTCSessionDescription, RTCConfiguration, RTCIceServer
        from aiortc.contrib.media import MediaPlayer
        from backend.stream import SubtitleTrack
    except ImportError as exc:
        raise HTTPException(503, 'Install requirements-stream.txt for WebRTC') from exc
    pc = RTCPeerConnection(RTCConfiguration(iceServers=[RTCIceServer(**s) for s in ice_servers()]))
    peers.add(pc)
    player = None
    track = None

    @pc.on('connectionstatechange')
    async def cleanup():
        if pc.connectionState in ('failed','closed','disconnected'):
            if track:
                track.stop()
            if player and player.video:
                player.video.stop()
            if pc.connectionState != 'closed':
                await pc.close()
            peers.discard(pc)
    try:
        player = MediaPlayer(os.environ['DISPLAY_SOURCE'], format='x11grab', options={'video_size':os.getenv('VIDEO_SIZE','1280x720'),'framerate':'20'})
        track = SubtitleTrack(player.video, translate, read_text)
        pc.addTrack(track)
        await pc.setRemoteDescription(RTCSessionDescription(sdp=payload.sdp,type=payload.type))
        await pc.setLocalDescription(await pc.createAnswer())
        async def expire_unconnected():
            await asyncio.sleep(30)
            if pc.connectionState not in ('connected','closed'):
                await pc.close()
        asyncio.create_task(expire_unconnected())
        return {'sdp':pc.localDescription.sdp,'type':pc.localDescription.type}
    except Exception as exc:
        await pc.close()
        if track:
            track.stop()
        if player and player.video:
            player.video.stop()
        peers.discard(pc)
        raise HTTPException(503, 'Display capture failed; check Linux display and video dependencies') from exc


app.mount('/', StaticFiles(directory=ROOT / 'dist', html=True), name='site')
