# Parallel Arcade | باراليل

**An Arabic/English interactive gaming lab and a self-hosted cloud-gaming integration kit.**

واجهة ألعاب تفاعلية عربية وإنجليزية، مع تجربة أصلية قابلة للعب وخادم لترجمة النصوص الإنجليزية إلى العربية.

## What is actually implemented?

This repository is an **MVP / integration foundation**, not a universal cloud emulator or a production multi-tenant SaaS. It includes no commercial games, BIOS files, ROMs, or game-specific memory adapters.

| Capability | Delivered behavior |
|---|---|
| Arabic / English | Full RTL/LTR interface, remembered language preference |
| Original browser game | Neon Expedition: keyboard/touch controls, eight collectibles, portal and obstacles |
| NPC mind-jacking | Three NPCs can be controlled in the original demo; their own movement pauses while controlled |
| Live modifiers | Temporary wall-phasing (“zero gravity”), double speed, tank obstacle in the top-down demo |
| Rewind | Local in-memory snapshots every 30 seconds; restore a snapshot at least 60 seconds old; available after 60 seconds of active play |
| Arabic demo subtitles | Authored dialogue, clearly labeled as prewritten; not AI output |
| Actual translation | Authenticated Python endpoint uses a locally installed Argos English → Arabic model |
| Screenshot / window OCR | Tesseract English OCR, local translation, Arabic overlay, export SRT; window capture samples every 3 seconds |
| Server-side subtitles | Optional Linux WebRTC video capture burns reshaped Arabic into frames before transmission |
| ISO + JSON upload | Authenticated storage with profile validation; **does not launch the ISO** |
| Shared room | Up to eight trusted clients relay player positions; peers appear as cyan markers in the demo |
| Python parallel sync client | Relays positions between room and a separately implemented local HTTP adapter |
| IoT | Local light preview; fixed admin-configured webhook for shared-room energy events |
| Classic-game mind-jacking / mods / savestates | Adapter interface supplied; actual emulator/game adapter **not implemented** |
| Cloud audio / game input | **Not implemented**; optional stream is video only |
| Full game-state multiplayer | **Not implemented**; coordinate relay alone does not sync enemies, missions, physics or collectibles |
| Accounts, billing, matchmaking | **Not implemented**; this is a single-operator trusted-room gateway |

Nothing here promises that “any ISO + a few addresses” works. Addresses, entity ownership, AI state, controller routing, savestates and spawn functions depend on the exact game and emulator build. Runtime latency is hardware/network dependent; sub-second AI translation is not guaranteed.

## 1. Try the site immediately

Open `dist/index.html` in a modern desktop browser, or serve the directory:

```bash
python -m http.server 8080 --directory dist
```

Visit `http://localhost:8080`. No build step is required. Arabic is the default. Fonts use Google Fonts with local fallbacks; gameplay itself needs no external library.

Move with WASD / arrows or mobile buttons. Collect eight amber shards, then reach the top portal. Select ECHO, NOVA or ATLAS in the radar to control them. Only the main player collects shards. Rewind unlocks after 60 active seconds. Closing/reloading the page loses demo state. Moving to another tab pauses gameplay. Use the pause button to resume.

## 2. Run real English → Arabic translation

Requirements: Docker Compose, free disk for the model and uploads; an internet connection once to install images/packages/model.

```bash
cp .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Replace `PARALLEL_TOKEN` in `.env` with the generated token. Placeholder tokens are refused.

```bash
docker compose up --build -d
docker compose exec gateway python backend/install_model.py
```

1. Open `http://localhost:8000`.
2. Open **Server & sync / الخادم والتزامن**.
3. Set server URL to `http://localhost:8000` and paste your token. Click **Test connection**.
4. Open **Translation studio**. Translate text, upload a screenshot, or share a game window.
5. Allow the browser's capture prompt. This version reads **visible English text**, not spoken dialogue. It sends screenshots to your configured server. Stop sharing to end capture.

Translation runs locally after model installation. Accuracy varies, especially with stylized fonts, proper names, menus and mixed-language scenes. SRT times are relative to the first translation event, not an existing movie timeline. Window capture requires a supported secure-context desktop browser; screenshot upload is the mobile fallback.

### Native Python alternative (Linux)

Install Tesseract with English data and DejaVu fonts using your OS package manager, then:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python backend/install_model.py
export PARALLEL_TOKEN='your-generated-token'
export ALLOWED_ORIGINS='http://localhost:8000,http://127.0.0.1:8000'
uvicorn backend.app:app --host 127.0.0.1 --port 8000 --ws-max-size 65536
```

Native execution does not automatically load `.env`; export variables in your shell. Docker Compose loads it.

## 3. Optional Linux emulator video + server-burned Arabic

This is separate from the default Docker setup. Use a native Linux host with your installed, licensed emulator already running on an X11 display. A headless host can use a separately configured Xvfb display. The application does **not** install or launch an emulator.

```bash
pip install -r requirements-stream.txt
export DISPLAY_SOURCE=':99.0'
export VIDEO_SIZE='1280x720'
export OCR_CROP_TOP='0.55'
# export PARALLEL_TOKEN and ALLOWED_ORIGINS as above
uvicorn backend.app:app --host 127.0.0.1 --port 8000 --ws-max-size 65536
```

The capture display must actually exist at the configured resolution and be accessible by this process. Click **Start server stream**. Tesseract samples the lower 45% every three seconds; Argos translates; Pillow/Arabic reshaper draws Arabic into video frames before aiortc encodes them. Errors appear in server logs; video continues without subtitles if OCR fails. No audio track or emulator input channel is provided. The browser's “Arabic subtitles” switch controls only the local demo overlay, not subtitles already burned into server frames.

Across networks, configure a TURN server using `TURN_URL`, `TURN_USERNAME`, `TURN_PASSWORD`. HTTPS and a proxy allowing WebSocket upgrades are needed for a public host. ICE success depends on firewall/NAT settings. The default compose container does not include X11/WebRTC dependencies or display access.

## 4. ISO library and per-game profiles

Use games you have permission to run. Never commit ISOs or BIOS files to GitHub.

Select an ISO and a JSON profile based on `examples/game-profile.json`. Files remain on your device until **Upload to server** is clicked. The server saves opaque random filenames under its data volume and never executes uploaded content. Maximum ISO size defaults to 8 GiB; adjust `MAX_ISO_BYTES` and proxy limits together. Upload is not resumable; keep the tab open. This is a simple ingestion endpoint, not a complete media manager.

A real adapter must verify the ISO hash/version before doing anything with memory. The supplied `GameAdapter` protocol documents required operations. Implement, test, and pin the adapter against a specific emulator release and game revision. The gateway does not execute profile commands, write process memory, or fabricate support for unknown games.

## 5. Shared rooms and local emulator bridge

All room users need the same server and token; this is for trusted testing. Use a hard-to-guess room code. The gateway checks allowed browser origins and authenticates the WebSocket's first message. Tokens are never placed in URLs or localStorage. Room state is ephemeral and disappears on restart; run **one** gateway worker.

Each browser demo is its own world. Only positions and energy events relay; a cyan peer marker is not a full co-op NPC. No frame-perfect or authoritative world simulation is claimed.

For a local emulator, implement a local HTTP adapter:

- `GET /player` → `{"x": 10, "y": 20, "z": 0}`
- `POST /peers` ← `{"peer-id":{"x":10,"y":20,"z":0}}`

The adapter is responsible for mapping coordinates, creating/despawning a remote NPC, interpolation, and game-version validation. Then run:

```bash
export PARALLEL_TOKEN='your-generated-token'
python backend/sync_client.py --server ws://localhost:8000 --room your-room --adapter http://127.0.0.1:8765
```

Use `wss://` outside a trusted local environment. Do not expose the local adapter publicly. The client fails visibly if the adapter is absent; it does not pretend to read emulator memory.

## 6. IoT and rewind

`IOT_WEBHOOK_URL` is an admin-set endpoint for your own automation system. Optional `IOT_WEBHOOK_TOKEN` becomes a Bearer header. Shared-room energy events send `{"event":"energy","color":"#b99bff","duration_ms":400}` with a rate limit per client. Adapt this payload to your lighting system. Destination URLs cannot be supplied from the web interface. The on-screen LED works without hardware and is a preview only.

Browser rewind restores game state from memory. **It does not rewind a server emulator or video buffer.** For classic games, implement `save_state`/`load_state` in the adapter, add a server-side snapshot scheduler and reset the stream after restoring. Decide host permissions/voting before exposing shared rewind. The current rewind button is disabled while streaming.

## 7. GitHub and deployment

Create an empty repository, extract this bundle into it, then:

```bash
git init
git add .
git commit -m "Build Parallel Arcade bilingual MVP"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/parallel-arcade.git
git push -u origin main
```

To publish the interface through GitHub Pages:

1. In repository **Settings → Pages**, select **GitHub Actions** as source.
2. In **Actions**, run **Deploy interface to GitHub Pages**.
3. Open the deployment URL displayed by the workflow.

GitHub Pages serves the demo/interface only. It cannot run Python, an emulator, OCR or WebRTC capture. Deploy the gateway separately, set `ALLOWED_ORIGINS` to the **exact HTTPS interface origin**, and use that gateway URL in the UI. No wildcard origins by default. A hosted HTTPS interface cannot use a plain HTTP gateway; for local HTTP development, use the interface served by the gateway instead.

The downloadable source link is bundled in the hosted release. To regenerate it after editing:

```bash
python package_release.py
```

## 8. Project structure

```text
dist/                 Static bilingual website and original canvas game
backend/app.py        Auth, OCR, translation, uploads, rooms, WebRTC signaling
backend/stream.py     OCR + Arabic text burned into captured frames
backend/adapter.py    Per-game adapter contract (implementation required)
backend/sync_client.py Local adapter ↔ room relay
backend/install_model.py  One-time Argos package download
examples/             Game profile schema example
.github/workflows/    Syntax/API checks and manual GitHub Pages deploy
Dockerfile            Translation/room gateway image
compose.yaml          Local-only gateway + persistent volumes
.env.example          Configuration without secrets
SECURITY.md           Deployment boundaries and reporting
TESTING.md            What was checked and what remains unverified
```

## 9. Before production

This project deliberately does not claim production readiness. Add user identities, tenant isolation, quotas, per-room roles, authenticated controller ownership, rate-limited translation workers, upload accounting/cleanup, emulator sandboxing, monitoring and database-backed orchestration. Put an explicit body-size limit and rate limits in your reverse proxy. Never expose the trusted-room token as a public shared credential. Account for game-streaming rights and translation-model licenses separately from this code's MIT license.

The CPU model can be slow. Run a bounded translation queue for multiple users; do not promise a fixed latency. Four optional video peers is a simple resource cap, not a capacity guarantee.

## بالعربي — البداية السريعة

- افتح `dist/index.html` لتجربة اللعبة والواجهة فوراً.
- اللعبة الأصلية، التحكم بالشخصيات، المودات وإعادة الزمن تعمل في المتصفح.
- لترجمة ألعابك فعلياً: شغّل الخادم بـ Docker، ثبّت النموذج، ثم اربطه من صفحة الخادم.
- الترجمة تقرأ النص الإنجليزي الظاهر بالشاشة؛ لا تترجم الصوت.
- ملفات ISO تُحفظ فقط؛ تشغيلها يحتاج محاكياً وموصلاً خاصاً باللعبة، غير مضمّنين.
- بث الفيديو الحقيقي اختياري على Linux. لا يوجد صوت أو تحكم سحابي باللعبة في هذه النسخة.
- رفع الملفات إلى GitHub لا يشغّل الخادم. GitHub Pages يستضيف الواجهة فقط.
- لا ترفع `.env` أو الألعاب أو BIOS أو مفاتيح الوصول إلى GitHub.

## Technical references

- [Argos Translate](https://github.com/argosopentech/argos-translate)
- [aiortc API](https://aiortc.readthedocs.io/en/latest/api.html)
- [aiortc media helpers](https://aiortc.readthedocs.io/en/latest/helpers.html)

MIT licensed code. Dependencies retain their own licenses.
