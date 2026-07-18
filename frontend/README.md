# Healeka Voice Console

Admin UI to onboard multiple hospitals onto the AI voice agent.

## Features

- Login with `ADMIN_API_KEY`
- List / create / edit / enable / delete hospital tenants
- Configure Plivo DIDs, HMS URL/subdomain/JWT, voice, transfer number
- View recent call logs per hospital

## Run locally

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173  
Sign in with the same `ADMIN_API_KEY` as the API `.env`.

By default (`.env.development`) Vite proxies `/admin` to  
`https://voice-agent.lalluvemula.cloud`.

For a local API instead:

```bash
# terminal 1 — API
uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload

# terminal 2 — dashboard
cd frontend
echo 'VITE_PROXY_TARGET=http://127.0.0.1:8080' > .env.development.local
npm run dev
```

## Production

```bash
cd frontend
npm install
npm run build
```

Serve `dist/` with nginx, or set `VITE_API_BASE_URL=https://voice-agent.lalluvemula.cloud` before build.

Ensure API `.env` includes your dashboard origin:

```env
CORS_ORIGINS=https://voice-console.yourdomain.com,http://localhost:5173
```
