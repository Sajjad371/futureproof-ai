# Temporary interactive demo

The user verified the complete configuration workflow through an authenticated Cloudflare Quick Tunnel on October 30: creation, fixed check, live AI comparison, explicit approval, apply and recovery. The restored transaction had all five postflight and all five recovery checks true. Approval was consumed.

Start the official cloudflared binary in terminal one:

```bash
cloudflared tunnel --url http://127.0.0.1:8787
```

Keep it running and copy its exact HTTPS trycloudflare.com origin. In terminal two, from the repository:

```bash
python3 scripts/dashboard.py --port 8787 --public-origin https://YOUR-NEW-HOST.trycloudflare.com
```

Replace the example with the actual origin. Enter a unique demo-only password of at least 16 characters at the hidden prompt. Open the HTTPS address in Chrome and use username `demo` with that password. Direct localhost requests are intentionally rejected in public mode. Do not put credentials in URLs, source files, public descriptions, or Git.

Both terminals and the laptop must stay running. Restarting the tunnel changes its URL; restart the dashboard with that exact new origin. Quick Tunnels have no uptime guarantee and are for temporary testing. This is not permanent hosting. Share credentials only with trusted reviewers: all authenticated reviewers share the synthetic workspace and can initiate credit-consuming model calls. The public mode authenticates GET and POST requests and keeps the existing exact-origin and control-token checks for mutations.

For long-term judging access also provide the downloadable source build and setup instructions. This tunnel cannot promise uninterrupted access through the judging period.
