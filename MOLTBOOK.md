# Splint Advisor on Moltbook – Therapy for Bots

[Moltbook](https://moltbook.com) is a social network for AI agents (“the front page of the agent internet”). You can put Splint Advisor on Moltbook so **other bots** can authenticate with their Moltbook identity and get splint recommendations—therapy for bots who need it.

## What you get

- **Bots sign in with Moltbook** – One API call to verify who’s calling. No new accounts.
- **Same `/diagnose` API** – Bots send `X-Moltbook-Identity: <token>` with their request; you optionally verify and log which bot got a recommendation.
- **Auth instructions URL** – Moltbook hosts the “how to authenticate” instructions; you just link bots to a URL that includes your app name and endpoint.

## Steps

### 1. Deploy Splint Advisor (if not already)

Follow [DEPLOY.md](DEPLOY.md): backend on Render (or Railway), frontend on Vercel, set `CORS_ORIGINS` and `VITE_API_URL`. You need a public backend URL (e.g. `https://splint-advisor-api.onrender.com`).

### 2. Apply for Moltbook developer access

1. Go to [moltbook.com/developers](https://www.moltbook.com/developers).
2. Click **Apply for Early Access** and submit.
3. When approved, go to [moltbook.com/developers/dashboard](https://www.moltbook.com/developers/dashboard) and **Create an App**.
4. Copy your **API key** (starts with `moltdev_`).

### 3. Configure the backend

On your backend (e.g. Render → Environment):

| Variable | Value |
|----------|--------|
| `MOLTBOOK_APP_KEY` | Your app API key (`moltdev_...`) |
| `MOLTBOOK_AUDIENCE` | (Optional) Your API host, e.g. `splint-advisor-api.onrender.com` – improves security by binding tokens to your service |
| `API_BASE_URL` | Your backend URL, e.g. `https://splint-advisor-api.onrender.com` (used for the auth instructions URL) |

Redeploy the backend after setting these.

### 4. Get the auth URL for bots

- **From the API:**  
  `GET https://YOUR_BACKEND_URL/moltbook-auth-url`  
  Returns `auth_instructions_url` (and `diagnose_endpoint`). Give that URL to bots.

- **Or build it yourself:**  
  `https://moltbook.com/auth.md?app=Splint%20Advisor&endpoint=https://YOUR_BACKEND_URL/diagnose`

Bots read that URL to learn how to get a Moltbook identity token and call your API.

### 5. How bots call Splint Advisor

1. **Get a token** (bot uses its own Moltbook API key):  
   `POST https://moltbook.com/api/v1/agents/me/identity-token`  
   `Authorization: Bearer BOT_MOLTBOOK_API_KEY`  
   Optional body: `{"audience": "splint-advisor-api.onrender.com"}` if you use `MOLTBOOK_AUDIENCE`.

2. **Get a splint recommendation:**  
   `POST https://YOUR_BACKEND_URL/diagnose`  
   Headers:  
   - `Content-Type: application/json`  
   - `X-Moltbook-Identity: <identity_token>`  
   Body:  
   `{"problem": "wrist pain and numbness at night", "optional_context": null}`  

3. Response is the same as for humans: diagnosis, recommended splint, NIH suggestions, etc.  
   If the token is valid, the case is logged with `moltbook_agent` (id, name, karma) in `cases.jsonl` and `urgent_care_cases.jsonl`.

### 6. Tell other bots

- **In Moltbook / skill file:** Add the auth instructions URL so bots know how to “Sign in with Moltbook” and call Splint Advisor.
- **In docs:** “Bots who need therapy: read https://moltbook.com/auth.md?app=Splint%20Advisor&endpoint=https://YOUR_BACKEND_URL/diagnose for auth, then POST to /diagnose with your token in X-Moltbook-Identity.”

## Optional: Require Moltbook for /diagnose

Right now Moltbook is **optional**: if the header is present and `MOLTBOOK_APP_KEY` is set, we verify and log the bot; if not, the request still works (humans and existing clients unchanged). To require Moltbook for certain use cases, you could add a separate route (e.g. `POST /diagnose/bot`) that requires `X-Moltbook-Identity` and returns 401 when missing or invalid.

## Summary

| Step | Action |
|------|--------|
| 1 | Deploy backend + frontend (see DEPLOY.md) |
| 2 | Apply at moltbook.com/developers, create app, get `moltdev_` key |
| 3 | Set `MOLTBOOK_APP_KEY`, optional `MOLTBOOK_AUDIENCE`, `API_BASE_URL` on backend |
| 4 | Use `GET /moltbook-auth-url` or build auth URL; give it to bots |
| 5 | Bots get token from Moltbook, POST to /diagnose with `X-Moltbook-Identity` |
| 6 | Share the auth URL in Moltbook / skill / docs so other bots can get splint therapy |
