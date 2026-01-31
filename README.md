# Splint Advisor – Upper Extremity

AI agent with a UI for PAs/urgent care: submit an upper extremity problem, get a diagnosis and splint recommendation, **NIH/PubMed-based suggestions**, and **other recommendations** (e.g. X-ray, ortho referral). All cases are logged as JSON for physician and **urgent care fine-tuning**. **Submit to manufacturing** opens a site to locate a printer (by IP/location).

## What it does

- **Submit problems** – Describe symptoms or injury (e.g. “wrist pain and numbness at night”, “thumb pain at base”).
- **Get recommendations** – Suggests an upper extremity splint, **suggested diagnosis (PA/urgent care)**, and **other recommendations** (imaging, referral, wound care) when more than a splint is needed.
- **NIH dataset search** – Queries PubMed (NIH/NCBI) for orthopaedic/splint literature and suggests **additional splints** and **diagnosis-related terms** from that evidence.
- **Submit to manufacturing** – Button opens a site to **locate printer by IP** (or nearby 3D printing services). URL is configurable via `MANUFACTURING_SITE_URL`.
- **JSON logging** – Every case is written to:
  - `cases.jsonl` and `fine_tune_dataset.jsonl` (physician fine-tuning)
  - **`urgent_care_cases.jsonl`** (urgent care / PA fine-tuning: suggested_diagnosis, other_recommendations, NIH data)

## Quick start

### 1. Backend (Python)

```bash
cd splint-advisor/backend
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Optional: for AI-powered diagnosis, set your OpenAI API key:

```bash
cp .env.example .env
# Edit .env and set OPENAI_API_KEY=sk-your-key
```

Optional: custom “locate printer” URL:

```bash
# In .env: MANUFACTURING_SITE_URL=https://your-printer-locator-site.com
```

Start the API:

```bash
uvicorn main:app --reload --port 8000
```

Without an API key, the backend uses a rule-based fallback. NIH/PubMed search runs in both modes.

### 2. Frontend (React)

In a new terminal:

```bash
cd splint-advisor/frontend
npm install
npm run dev
```

Open **http://localhost:5173**. Enter a problem, submit, then use **Submit to manufacturing** to open the printer-locator site.

## JSON for physician and urgent care fine-tuning

- **`backend/data/cases.jsonl`** – Full case log: `case_id`, `timestamp`, `input`, `output` (diagnosis, splint, NIH, other_recommendations). Use for review and analytics.
- **`backend/data/fine_tune_dataset.jsonl`** – Same cases in OpenAI-style messages format for model fine-tuning.
- **`backend/data/urgent_care_cases.jsonl`** – **Urgent care / PA fine-tuning**: each line has `suggested_diagnosis`, `other_recommendations`, `recommended_splint`, `nih_articles`, `additional_splints_from_nih`, `suggested_diagnosis_terms_from_nih`. Your team can correct these fields and use the file for urgent-care–specific fine-tuning.

API endpoints:

- `GET /cases` – List recent cases.
- `GET /cases/urgent-care` – List recent urgent care cases.
- `GET /export/fine-tune` – Info about physician fine-tuning dataset.
- `GET /export/urgent-care` – Info about urgent care fine-tuning dataset.
- `GET /nih-search?q=...` – Standalone NIH/PubMed search for orthopaedic/splint literature.
- `GET /manufacturing-url?ip=...` – URL to open for “locate printer by IP” (optional `ip` query param).

## Putting it online (so friends can test)

See **[DEPLOY.md](DEPLOY.md)** for step-by-step instructions:

1. **Backend** on [Render](https://render.com) (free) or [Railway](https://railway.app).
2. **Frontend** on [Vercel](https://vercel.com) (free), with `VITE_API_URL` set to your backend URL.
3. Set **CORS_ORIGINS** on the backend to your Vercel frontend URL.
4. Share the Vercel link with friends.

## Making it an online app (summary)

1. **Backend**: Deploy the FastAPI app (e.g. Render, Railway). Set `OPENAI_API_KEY`, `CORS_ORIGINS`, and optionally `MANUFACTURING_SITE_URL`.
2. **Frontend**: Deploy to Vercel/Netlify with **Root Directory** = `frontend` and **VITE_API_URL** = your backend URL.
3. **CORS**: Set `CORS_ORIGINS` on the backend to your frontend URL (comma-separated if you have several).

## Disclaimer

This is an advisory tool only. Recommendations must be confirmed by a qualified clinician before use.
