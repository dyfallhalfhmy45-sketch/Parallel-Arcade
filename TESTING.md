# Verification record — 2026-10-01

Passed:
- `node --check dist/app.js` and `node --check dist/hub.js`.
- `python -m compileall -q backend`.
- Eleven FastAPI TestClient tests (v0.2): token requirement, missing-model error, profile/upload validation, invalid image rejection, image/OCR response pipeline, two-client coordinate relay, missing display rejection, crop selection/validation, array-profile rejection, truthful service readiness, and actual body-size enforcement with a false Content-Length.
- Node + LinkeDOM logic harness: page initialization, three NPC controls, RTL/LTR toggle, collision geometry, shard collection, NPC movement, modifier expiry, 30-second snapshots and 60-second rewind.
- Local HTML CSS/JS/favicon references and JSON example parsed.
- Real Tesseract OCR on a synthetic high-contrast dialogue image: correctly read “Find the key and open the gate.” from the bottom region.
- Platform default screen, official Xbox setup link and missing-service gating checked in the DOM harness.

The OCR pipeline test uses mocked OCR/translation functions. It verifies request handling and response wiring, not translation quality. No Argos model was downloaded in this build environment. Real OCR was verified on one synthetic image, not commercial-game screenshots. The Docker launcher was syntax-checked, not run end-to-end here. Arabic inference, X11 display capture, WebRTC network traversal, physical IoT devices and emulator adapters were not run here.

No visual browser QA was available in this environment; layout is responsive by CSS but still needs checking on target browsers/devices. LinkeDOM is a DOM/logic harness, not a browser rendering test.

To repeat API tests:

```bash
pip install fastapi httpx python-multipart Pillow
python -m unittest discover -s tests -v
```

Before using real games: install model, translate known sentences, check Arabic shaping, test a real screenshot and target X11 display, verify TURN from a second network, and validate the adapter against one exact game build. No commercial-game support is asserted by these checks.
