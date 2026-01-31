# Deploy Splint Advisor — do each step in order

Do **Step 1**, then **Step 2**, and so on. When you see **You do:**, do that before going to the next step.

---

## Step 1 — Open Terminal and go to the project

**You do:**  
Open Terminal (or Cursor’s terminal) and run:

```bash
cd /Users/ashkan/splint-advisor
```

---

## Step 2 — Initialize Git and make the first commit

**You do:**  
Run these commands one after the other:

```bash
git init
git branch -M main
git add .
git status
```

You should see a list of files (backend, frontend, README, etc.). Then run:

```bash
git commit -m "Splint Advisor app"
```

You should see something like “X files changed”.

---

## Step 3 — Create a new repo on GitHub

**You do:**

1. Open a browser and go to: **https://github.com/new**
2. If you’re not logged in, log in to GitHub.
3. **Repository name:** type `splint-advisor` (or any name you like).
4. Leave **Public** selected.
5. **Do not** check “Add a README” or “Add .gitignore” (you already have them).
6. Click **Create repository**.

---

## Step 4 — Connect your folder to GitHub and push

On the new repo page, GitHub shows “…or push an existing repository from the command line.”  
**You do:**  
In Terminal, run (replace `YOUR_USERNAME` with your GitHub username):

```bash
git remote add origin https://github.com/YOUR_USERNAME/splint-advisor.git
git push -u origin main
```

If it asks for login, use your GitHub username and a **Personal Access Token** (not your password).  
To create a token: GitHub → Settings → Developer settings → Personal access tokens → Generate new token; give it “repo” scope.

After this, your code is on GitHub.

---

## Step 5 — Deploy the backend on Render

**You do:**

1. Go to **https://render.com** and sign up (or log in). Use **“Sign up with GitHub”**.
2. In the dashboard, click **New +** → **Web Service**.
3. Under “Connect a repository”, find **splint-advisor** and click **Connect** (or “Configure account” if it asks for repo access).
4. After it’s connected, click **splint-advisor** so it’s selected, then click **Connect** at the bottom.
5. Fill the form exactly like this:

   | Field | What to enter |
   |-------|-------------------------------|
   | **Name** | `splint-advisor-api` (or any name) |
   | **Region** | Choose closest to you |
   | **Root Directory** | `backend` |
   | **Runtime** | `Python 3` |
   | **Build Command** | `pip install -r requirements.txt` |
   | **Start Command** | `uvicorn main:app --host 0.0.0.0 --port $PORT` |

6. Scroll to **Environment** (or **Environment Variables**).
   - Click **Add Environment Variable**.
   - **Key:** `OPENAI_API_KEY`  
   - **Value:** your OpenAI API key (from https://platform.openai.com/api-keys).  
   - If you don’t have one, you can skip this; the app will use rule-based answers.
7. Scroll down and click **Create Web Service**.
8. Wait until the deploy finishes (log shows “Your service is live” or a green check).
9. At the top of the page you’ll see a URL like **https://splint-advisor-api.onrender.com**.  
   **Copy that URL** and keep it — you need it for the next steps.  
   This is your **backend URL**.

---

## Step 6 — Deploy the frontend on Vercel

**You do:**

1. Go to **https://vercel.com** and sign up (or log in). Use **“Continue with GitHub”**.
2. Click **Add New…** → **Project**.
3. Import your **splint-advisor** repo (if you don’t see it, click “Adjust GitHub App Permissions” and allow Vercel to see your repos).
4. After you select **splint-advisor**, you’ll see project settings. Set:

   | Field | What to enter |
   |-------|-------------------------------|
   | **Root Directory** | Click **Edit**, then type `frontend` and confirm. |
   | **Framework Preset** | Vite (should auto-detect). |
   | **Build Command** | Leave default: `npm run build` |
   | **Output Directory** | Leave default: `dist` |

5. Under **Environment Variables**, click **Add** (or “Add new”):
   - **Name:** `VITE_API_URL`
   - **Value:** paste the **backend URL** from Step 5 (e.g. `https://splint-advisor-api.onrender.com`) — **no trailing slash**.
6. Click **Deploy**.
7. Wait until the build finishes. You’ll get a URL like **https://splint-advisor-xxxx.vercel.app**.  
   **Copy that URL** — this is your **frontend URL** (the one you’ll share with friends).

---

## Step 7 — Allow the frontend in the backend (CORS)

**You do:**

1. Go back to **Render** (https://dashboard.render.com).
2. Open your **splint-advisor-api** (or whatever you named it) service.
3. Go to the **Environment** tab.
4. Click **Add Environment Variable**:
   - **Key:** `CORS_ORIGINS`
   - **Value:** paste your **frontend URL** from Step 6 (e.g. `https://splint-advisor-xxxx.vercel.app`) — **no trailing slash**.
5. Click **Save Changes**. Render will redeploy automatically; wait until it’s live again.

---

## Step 8 — Test and share

**You do:**

1. Open your **frontend URL** (the Vercel one) in your browser.
2. Type a problem (e.g. “wrist pain at night”) and click **Get splint recommendation**.
3. If you see a recommendation, it’s working.
4. If you see a network or CORS error, double-check:
   - **VITE_API_URL** on Vercel = your Render backend URL.
   - **CORS_ORIGINS** on Render = your Vercel frontend URL (exactly, no typo, no trailing slash).

**Share with friends:**  
Send them the **Vercel URL** (e.g. `https://splint-advisor-xxxx.vercel.app`). They can open it and test.

---

## Quick reference

| What | Where |
|------|--------|
| Backend URL | Render dashboard → your service → top of page |
| Frontend URL | Vercel project → “Visit” or the *.vercel.app link |
| Change API key | Render → your service → Environment → edit `OPENAI_API_KEY` |
| Change CORS | Render → your service → Environment → edit `CORS_ORIGINS` |

**Note:** On Render’s free plan the backend sleeps after ~15 minutes of no use. The first request after that may take 30–60 seconds; then it’s fast again.
