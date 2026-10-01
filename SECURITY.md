# Security scope

This is a trusted single-operator MVP. Do not deploy as an unrestricted public SaaS.

- Keep PARALLEL_TOKEN random and secret; all holders can translate, upload and join rooms.
- Browser origins are allowlisted. WebSockets authenticate in their first frame, not the URL.
- The token is kept in page memory only. The server URL and UI language are local preferences.
- Use HTTPS/WSS off localhost, reverse-proxy body/rate limits, disk quotas and a private gateway network.
- ISO uploads are opaque files, never executed; UUID filenames prevent path traversal.
- Uploaded files and models are excluded from git; no arbitrary memory write API is exposed.
- IoT destination is set by the operator, not a browser-provided URL. Use a narrowly scoped webhook.
- Screen sharing sends images to the configured gateway. Share only the intended game window.
- This version has no tenant/account isolation or role separation. A room code is not an authorization boundary.
- Report vulnerabilities privately to the repository owner; do not include secrets in public issues.
