# Verification record — 2026-10-01

Passed:
- `node --check dist/app.js`.
- `python -m compileall -q backend`.
- Seven FastAPI TestClient tests: token requirement, missing-model error, profile/upload validation, invalid image rejection, image/OCR response pipeline, two-client coordinate relay, missing display rejection.
- Node + LinkeDOM logic harness: page initialization, three NPC controls, RTL/LTR toggle, collision geometry, shard collection, NPC movement, modifier expiry, 30-second snapshots and 60-second rewind.
- Local HTML CSS/JS/favicon references and JSON example parsed.

The OCR pipeline test uses mocked OCR/translation functions. It verifies request handling and response wiring, not translation quality. No Argos model was downloaded in this build environment. Actual Tesseract recognition, Arabic inference, X11 display capture, WebRTC network traversal, physical IoT devices and emulator adapters were not run here.

No visual browser QA was available in this environment; layout is responsive by CSS but still needs checking on target browsers/devices. LinkeDOM is a DOM/logic harness, not a browser rendering test.

To repeat API tests:

```bash
pip install fastapi httpx python-multipart Pillow
python -m unittest discover -s tests -v
```

Before using real games: install model, translate known sentences, check Arabic shaping, test a real screenshot and target X11 display, verify TURN from a second network, and validate the adapter against one exact game build. No commercial-game support is asserted by these checks.
