# Put Splint Advisor online (so friends can test)

Two parts: **backend** (API) and **frontend** (UI). Deploy each once, then share the frontend URL.

---

## Option 1: Render (backend) + Vercel (frontend) — recommended

### 1. Put your code on GitHub

If you haven’t already:

```bash
cd /Users/ashkan/splint-advisor
git init
git add .
git commit -m "Splint Advisor app"
```

Create a new repo on [github.com](https://github.com/new), then:

```bash
git remote add origin https://github.com/YOUR_USERNAME/splint-advisor.git
git branch -M main
git push -u origin main
```

---

### 2. Deploy the **backend** on Render (free)

1. Go to [render.com](https://render.com) and sign up (or log in with GitHub).
2. **New → Web Service**.
3. Connect the **splint-advisor** repo.
4. Set:
   - **Name:** `splint-advisor-api` (or any name).
   - **Root Directory:** `backend`.
   - **Runtime:** Python 3.
   - **Build command:** `pip install -r requirements.txt`
   - **Start command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. **Environment:**
   - `OPENAI_API_KEY` = your OpenAI key (optional; without it you get rule-based only).
   - (Optional) `MANUFACTURING_SITE_URL` = URL for “Submit to manufacturing”.
6. Click **Create Web Service**. Wait for the first deploy.
7. Copy the service URL, e.g. **`https://splint-advisor-api.onrender.com`**. You’ll use this as the frontend’s API URL.

---

### 3. Deploy the **frontend** on Vercel (free)

1. Go to [vercel.com](https://vercel.com) and sign up (or log in with GitHub).
2. **Add New → Project** and import the **splint-advisor** repo.
3. Set:
   - **Root Directory:** `frontend` (click “Edit” and set it).
   - **Framework Preset:** Vite.
   - **Build Command:** `npm run build` (default).
   - **Output Directory:** `dist` (default).
4. **Environment variable:**
   - Name: `VITE_API_URL`
   - Value: your **backend URL** from step 2, e.g. `https://splint-advisor-api.onrender.com`  
   (no trailing slash)
5. Click **Deploy**. When it’s done, you get a URL like **`https://splint-advisor-xxx.vercel.app`**.

---

### 4. Allow the frontend URL in the backend (CORS)

Back on **Render** → your backend service → **Environment**:

- Add: `CORS_ORIGINS` = `https://splint-advisor-xxx.vercel.app`  
  (use your real Vercel URL; you can add more origins separated by commas).

Save. Render will redeploy. After that, the browser will allow requests from your frontend to the API.

---

### 5. Share with friends

Send them the **Vercel URL** (e.g. `https://splint-advisor-xxx.vercel.app`). They can open it and test; the app will call your backend on Render.

**Note:** On Render’s free tier, the backend sleeps after ~15 min of no use. The first request after that may take 30–60 seconds; later ones are fast.

---

## Option 2: Backend on Railway instead of Render

1. Go to [railway.app](https://railway.app), sign in with GitHub.
2. **New Project → Deploy from GitHub** → choose **splint-advisor**.
3. Select the repo, then set **Root Directory** to `backend`.
4. Railway will detect Python. Set **Start Command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. In **Variables**, add `OPENAI_API_KEY` (and optionally `CORS_ORIGINS` and `MANUFACTURING_SITE_URL`).
6. In **Settings**, generate a **public domain** (e.g. `splint-advisor-api.up.railway.app`).
7. Use this URL as `VITE_API_URL` when deploying the frontend (Vercel, same as above), and set `CORS_ORIGINS` to your Vercel frontend URL.

---

## Checklist

| Step | What |
|------|------|
| 1 | Repo on GitHub |
| 2 | Backend on Render (or Railway) → copy backend URL |
| 3 | Frontend on Vercel with `VITE_API_URL` = backend URL |
| 4 | Backend env `CORS_ORIGINS` = your Vercel frontend URL |
| 5 | Share Vercel link with friends |

---

## If something doesn’t work

- **“Network error” or CORS in browser:**  
  Make sure `CORS_ORIGINS` on the backend exactly matches your frontend URL (including `https://`, no trailing slash unless you use it in the app).
- **Backend “Application failed” on Render:**  
  Check **Logs**; often it’s a missing env var or wrong **Start command** (must use `$PORT`).
- **Frontend shows old API:**  
  Redeploy on Vercel after changing `VITE_API_URL` (build-time variable).
