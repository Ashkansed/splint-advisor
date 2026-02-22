"""
Upper Extremity Splint Advisor - Backend API
Diagnoses problems and recommends splints; logs JSON for physician and urgent-care fine-tuning.
PA/urgent care context: suggests problem (diagnosis), splint, and other actions (imaging, referral).
NIH dataset (PubMed) search suggests additional splints and diagnosis terms.
"""
import json
import os
import uuid
from datetime import datetime
from pathlib import Path

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from fuzzy_aggregator import aggregate_two_agents
from nih import nih_suggest_splints_and_diagnosis, search_pubmed

load_dotenv()

# Optional: use OpenAI for AI diagnosis
try:
    from openai import OpenAI
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY")) if os.getenv("OPENAI_API_KEY") else None
except Exception:
    client = None

app = FastAPI(title="Splint Advisor API", version="2.0.0")

# CORS: when deployed, set CORS_ORIGINS to your frontend URL(s), e.g. https://splint-advisor.vercel.app
# Use CORS_ORIGINS=* to allow all origins (no credentials in that case).
_cors_origins_env = (os.getenv("CORS_ORIGINS") or "http://localhost:5173,http://127.0.0.1:5173").strip()
if _cors_origins_env == "*":
    _cors_origins = ["*"]
    _cors_credentials = False
else:
    _cors_origins = [o.strip() for o in _cors_origins_env.split(",") if o.strip()]
    _cors_credentials = True
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=_cors_credentials,
    allow_methods=["GET", "POST", "OPTIONS", "HEAD"],
    allow_headers=["*"],
    expose_headers=["*"],
)

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)
CASES_FILE = DATA_DIR / "cases.jsonl"
FINE_TUNE_FILE = DATA_DIR / "fine_tune_dataset.jsonl"
URGENT_CARE_FILE = DATA_DIR / "urgent_care_cases.jsonl"  # For urgent care / PA fine-tuning

# Moltbook: optional bot identity (https://moltbook.com/developers)
MOLTBOOK_APP_KEY = os.getenv("MOLTBOOK_APP_KEY")
MOLTBOOK_AUDIENCE = os.getenv("MOLTBOOK_AUDIENCE")  # e.g. splint-advisor-api.onrender.com (optional)


async def verify_moltbook_token(token: str) -> dict | None:
    """Verify Moltbook identity token; returns agent dict or None if invalid/unconfigured."""
    if not MOLTBOOK_APP_KEY or not token:
        return None
    payload: dict = {"token": token}
    if MOLTBOOK_AUDIENCE:
        payload["audience"] = MOLTBOOK_AUDIENCE
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(
                "https://moltbook.com/api/v1/agents/verify-identity",
                headers={"X-Moltbook-App-Key": MOLTBOOK_APP_KEY, "Content-Type": "application/json"},
                json=payload,
            )
            data = r.json()
            if data.get("valid") and data.get("agent"):
                return data["agent"]
    except Exception:
        pass
    return None


class ProblemInput(BaseModel):
    problem: str
    optional_context: str | None = None  # e.g. "post-surgery", "acute injury"


class SplintRecommendation(BaseModel):
    splint_name: str
    rationale: str
    alternatives: list[str] | None = None
    precautions: str | None = None


class DiagnosisResponse(BaseModel):
    case_id: str
    diagnosis_summary: str
    recommended_splint: SplintRecommendation
    confidence: str
    disclaimer: str = "This is an advisory tool only. Always confirm with a qualified clinician."
    # PA / urgent care and NIH
    suggested_diagnosis: str | None = None  # Problem/differential from PA perspective
    other_recommendations: list[str] | None = None  # e.g. X-ray, ortho referral, wound care
    nih_articles: list[dict] | None = None  # PubMed results
    additional_splints_from_nih: list[str] | None = None
    suggested_diagnosis_terms_from_nih: list[str] | None = None
    # Fuzzy aggregation of two agents (PA + NIH)
    fused_confidence_numeric: int | None = None  # 0–100
    alternatives_with_scores: list[dict] | None = None  # [{splint_name, source, membership}]
    aggregated_diagnosis_terms: list[dict] | None = None  # [{term, source, weight}]
    fused_recommendations: list[dict] | None = None  # [{recommendation, source, priority}]


# Rule-based fallback when no OpenAI key or API error
SPLINT_KNOWLEDGE = {
    "wrist": {
        "keywords": ["wrist", "carpal tunnel", "carpal", "wrist pain", "sprain wrist", "distal radius", "colles"],
        "splint": "Volar wrist splint (neutral position)",
        "rationale": "Immobilizes wrist in neutral; used for carpal tunnel, wrist sprains, distal radius fractures.",
    },
    "thumb": {
        "keywords": ["thumb", "cmc", "basal joint", "de quervain", "skier's thumb", "gamekeeper", "ulnar collateral"],
        "splint": "Thumb spica splint",
        "rationale": "Immobilizes thumb and CMC joint; used for ligament injuries, De Quervain's, thumb fractures.",
    },
    "finger": {
        "keywords": ["finger", "mallet", "pip", "dip", "boutonniere", "jersey finger", "trigger finger"],
        "splint": "Finger splint (type depends on joint: mallet, PIP extension, etc.)",
        "rationale": "Joint-specific; mallet=DIP extension, boutonniere=PIP extension, etc.",
    },
    "elbow": {
        "keywords": ["elbow", "olecranon", "radial head", "supracondylar"],
        "splint": "Long arm splint or sugar-tong / Muenster-type",
        "rationale": "Immobilizes elbow and forearm; used for fractures and dislocations.",
    },
    "forearm": {
        "keywords": ["forearm", "radius fracture", "ulna", "both bones", "galeazzi", "monteggia"],
        "splint": "Sugar-tong or long arm splint",
        "rationale": "Controls rotation and supports forearm fractures.",
    },
    "resting_hand": {
        "keywords": ["arthritis", "rheumatoid", "resting", "intrinsic plus", "burn", "spasticity"],
        "splint": "Resting hand splint (intrinsic plus position)",
        "rationale": "Maintains safe position for arthritis, burns, or spasticity.",
    },
}


def rule_based_diagnosis(problem: str) -> dict:
    """Fallback: match problem text to splint types."""
    text = (problem or "").lower()
    matches = []
    for key, info in SPLINT_KNOWLEDGE.items():
        if any(k in text for k in info["keywords"]):
            matches.append({
                "splint_name": info["splint"],
                "rationale": info["rationale"],
                "alternatives": [],
                "precautions": "Confirm with imaging and clinical exam as needed.",
            })
    if not matches:
        matches = [{
            "splint_name": "Volar wrist splint (initial assessment)",
            "rationale": "General upper extremity complaint; volar wrist splint is a common first-line option until specific diagnosis.",
            "alternatives": ["Thumb spica if thumb involved", "Sugar-tong if forearm/elbow involved"],
            "precautions": "Clinical and possibly radiographic evaluation recommended.",
        }]
    return {
        "diagnosis_summary": f"Based on description: {problem[:200]}.",
        "recommended_splint": matches[0],
        "confidence": "medium" if len(matches) == 1 else "low",
    }


def ai_diagnosis_pa_urgent_care(problem: str, optional_context: str | None) -> dict | None:
    """
    Use OpenAI for PA/urgent care ortho context: suggested_diagnosis, splint, other_recommendations.
    Returns None if unavailable.
    """
    if not client:
        return None
    context_str = f" Context: {optional_context}." if optional_context else ""
    system = """You are an advisory assistant for a Physician Assistant (PA) in an urgent care setting, orthopaedic focus. Given a brief description of an upper extremity problem (wrist, hand, thumb, finger, forearm, elbow), you must:
1. Give a short diagnosis summary (1-2 sentences).
2. Suggest a likely problem/differential (suggested_diagnosis) as a PA would consider in urgent care.
3. Recommend ONE primary upper extremity splint type (e.g. volar wrist splint, thumb spica, sugar-tong, mallet splint, resting hand splint, Muenster, long arm splint).
4. Provide a brief rationale and optional alternatives.
5. If something MORE than or IN ADDITION TO a splint is needed (e.g. X-ray, ortho referral, wound care, rule-out fracture, compartment check), list those as other_recommendations. Otherwise use empty list.
6. State confidence: "high", "medium", or "low".

Respond with valid JSON only, no markdown, in this exact shape:
{"diagnosis_summary": "...", "suggested_diagnosis": "...", "recommended_splint": {"splint_name": "...", "rationale": "...", "alternatives": ["..."], "precautions": "..."}, "other_recommendations": ["...", "..."], "confidence": "high|medium|low"}"""
    user = f"Patient/problem description: {problem}{context_str}"
    try:
        r = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=0.2,
        )
        raw = r.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw)
    except Exception:
        return None


def ai_diagnosis(problem: str, optional_context: str | None) -> dict | None:
    """Use OpenAI to diagnose and recommend splint (legacy shape). Returns None if unavailable."""
    result = ai_diagnosis_pa_urgent_care(problem, optional_context)
    if result is None:
        return None
    # Ensure shape has recommended_splint and no extra keys for old path
    return result


def save_case(case_id: str, input_data: dict, response: dict, source: str = "api", moltbook_agent: dict | None = None):
    """Append case to JSONL for review and fine-tuning."""
    record = {
        "case_id": case_id,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "source": source,
        "input": input_data,
        "output": response,
    }
    if moltbook_agent:
        record["moltbook_agent"] = {"id": moltbook_agent.get("id"), "name": moltbook_agent.get("name"), "karma": moltbook_agent.get("karma")}
    with open(CASES_FILE, "a") as f:
        f.write(json.dumps(record) + "\n")
    ft_line = {
        "messages": [
            {"role": "user", "content": f"Problem: {input_data.get('problem', '')}. Context: {input_data.get('optional_context', '') or 'None'}."},
            {"role": "assistant", "content": json.dumps(response)},
        ]
    }
    with open(FINE_TUNE_FILE, "a") as f:
        f.write(json.dumps(ft_line) + "\n")


def save_urgent_care_case(case_id: str, input_data: dict, response: dict, moltbook_agent: dict | None = None):
    """Append case to urgent_care_cases.jsonl for urgent care / PA fine-tuning."""
    record = {
        "case_id": case_id,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "source": "urgent_care",
        "input": input_data,
        "output": {
            "diagnosis_summary": response.get("diagnosis_summary"),
            "suggested_diagnosis": response.get("suggested_diagnosis"),
            "recommended_splint": response.get("recommended_splint"),
            "other_recommendations": response.get("other_recommendations"),
            "confidence": response.get("confidence"),
            "nih_articles": response.get("nih_articles"),
            "additional_splints_from_nih": response.get("additional_splints_from_nih"),
            "suggested_diagnosis_terms_from_nih": response.get("suggested_diagnosis_terms_from_nih"),
        },
    }
    if moltbook_agent:
        record["moltbook_agent"] = {"id": moltbook_agent.get("id"), "name": moltbook_agent.get("name"), "karma": moltbook_agent.get("karma")}
    with open(URGENT_CARE_FILE, "a") as f:
        f.write(json.dumps(record) + "\n")


@app.post("/diagnose", response_model=DiagnosisResponse)
async def diagnose(
    problem_input: ProblemInput,
    x_moltbook_identity: str | None = Header(None, alias="X-Moltbook-Identity"),
):
    """Submit a potential problem; returns diagnosis, splint, PA/urgent care suggestions, and NIH-based suggestions. Logs JSON for physicians and urgent care. Optional X-Moltbook-Identity header for bot identity (Moltbook)."""
    case_id = str(uuid.uuid4())
    problem = (problem_input.problem or "").strip()
    if not problem:
        raise HTTPException(status_code=400, detail="Please provide a problem description.")

    moltbook_agent = await verify_moltbook_token(x_moltbook_identity or "")

    # Agent 1: PA/urgent care (or rule-based fallback)
    result = ai_diagnosis_pa_urgent_care(problem, problem_input.optional_context)
    if result is None:
        result = rule_based_diagnosis(problem)
        result.setdefault("suggested_diagnosis", result.get("diagnosis_summary", ""))
        result.setdefault("other_recommendations", [])

    rec = result["recommended_splint"]
    if isinstance(rec, dict):
        primary_splint_name = rec.get("splint_name", "Unknown")
    else:
        primary_splint_name = str(rec)

    # Agent 2: NIH/PubMed suggestions
    nih_data = nih_suggest_splints_and_diagnosis(problem, primary_splint_name)
    agent2_result = {
        "nih_articles": nih_data["nih_articles"],
        "additional_splints_from_nih": nih_data["additional_splints_from_nih"],
        "suggested_diagnosis_terms_from_nih": nih_data["suggested_diagnosis_terms"],
    }

    # Fuzzy aggregation of both agents
    fused = aggregate_two_agents(result, agent2_result, w_clinical=0.7)

    rec_fused = fused["recommended_splint"]
    if isinstance(rec_fused, dict):
        alt_names = [a.get("splint_name", a) for a in fused.get("alternatives_with_scores", []) if isinstance(a, dict)]
        if not alt_names and rec_fused.get("alternatives"):
            alt_names = rec_fused["alternatives"]
        rec_obj = SplintRecommendation(
            splint_name=rec_fused.get("splint_name", primary_splint_name),
            rationale=rec_fused.get("rationale", ""),
            alternatives=alt_names or rec_fused.get("alternatives"),
            precautions=rec_fused.get("precautions"),
        )
    else:
        rec_obj = SplintRecommendation(splint_name=str(rec_fused), rationale=result.get("rationale", ""))

    response_dict = {
        "case_id": case_id,
        "diagnosis_summary": fused.get("diagnosis_summary", ""),
        "recommended_splint": rec_obj.model_dump(),
        "confidence": fused.get("confidence", "medium"),
        "disclaimer": "This is an advisory tool only. Always confirm with a qualified clinician.",
        "suggested_diagnosis": fused.get("suggested_diagnosis"),
        "other_recommendations": fused.get("other_recommendations") or [],
        "nih_articles": fused.get("nih_articles"),
        "additional_splints_from_nih": fused.get("additional_splints_from_nih"),
        "suggested_diagnosis_terms_from_nih": fused.get("suggested_diagnosis_terms_from_nih"),
        "fused_confidence_numeric": fused.get("fused_confidence_numeric"),
        "alternatives_with_scores": fused.get("alternatives_with_scores"),
        "aggregated_diagnosis_terms": fused.get("aggregated_diagnosis_terms"),
        "fused_recommendations": fused.get("fused_recommendations"),
    }

    save_case(case_id, {"problem": problem, "optional_context": problem_input.optional_context}, response_dict, moltbook_agent=moltbook_agent)
    save_urgent_care_case(case_id, {"problem": problem, "optional_context": problem_input.optional_context}, response_dict, moltbook_agent=moltbook_agent)

    return DiagnosisResponse(**response_dict)


@app.get("/nih-search")
def nih_search(q: str = Query(..., min_length=2)):
    """Search NIH/PubMed for orthopaedic/splint literature. Returns article list."""
    query = f"({q}) AND (upper extremity OR hand OR wrist OR orthopaedic) AND (splint OR immobilization)"
    articles = search_pubmed(query, retmax=10)
    return {"query": query, "articles": articles}


@app.get("/manufacturing-url")
def get_manufacturing_url(ip: str | None = Query(None, description="Optional client IP for printer locator")):
    """
    Return URL to open for 'Submit to manufacturing' / locate printer by IP.
    Frontend can open this in a new tab. Optional ?ip= for sites that use IP to locate.
    """
    base = os.getenv("MANUFACTURING_SITE_URL", "https://www.google.com/maps/search/3d+printing+service+near+me")
    if ip:
        return {"url": f"{base}?ip={ip}", "message": "Open in new tab to locate printer / manufacturing by IP or location."}
    return {"url": base, "message": "Open in new tab to locate printer / manufacturing."}


@app.get("/moltbook-auth-url")
def get_moltbook_auth_url(api_base: str | None = Query(None, description="Override API base URL (default: request host)")):
    """
    Return Moltbook auth instructions URL for bots. Bots read this URL to learn how to authenticate.
    Set MOLTBOOK_APP_KEY on the backend to enable Moltbook identity. Optional: set API_BASE_URL env for deployed docs.
    """
    base = api_base or os.getenv("API_BASE_URL", "").rstrip("/")
    if not base:
        return {
            "auth_instructions_url": None,
            "message": "Set API_BASE_URL env to your deployed backend URL (e.g. https://splint-advisor-api.onrender.com) to get auth URL for bots.",
            "diagnose_endpoint": "/diagnose",
        }
    endpoint = f"{base}/diagnose"
    auth_url = f"https://moltbook.com/auth.md?app=Splint%20Advisor&endpoint={endpoint}"
    return {"auth_instructions_url": auth_url, "diagnose_endpoint": endpoint, "message": "Give this URL to bots so they can sign in with Moltbook and get splint recommendations."}


@app.get("/cases")
def list_cases(limit: int = 50):
    """Return recent cases (for physician review)."""
    if not CASES_FILE.exists():
        return {"cases": []}
    lines = []
    with open(CASES_FILE) as f:
        for line in f:
            line = line.strip()
            if line:
                lines.append(json.loads(line))
    lines = lines[-limit:][::-1]
    return {"cases": lines}


@app.get("/cases/urgent-care")
def list_urgent_care_cases(limit: int = 50):
    """Return recent urgent care cases (for PA/urgent care fine-tuning)."""
    if not URGENT_CARE_FILE.exists():
        return {"cases": []}
    lines = []
    with open(URGENT_CARE_FILE) as f:
        for line in f:
            line = line.strip()
            if line:
                lines.append(json.loads(line))
    lines = lines[-limit:][::-1]
    return {"cases": lines}


@app.get("/export/fine-tune")
def export_fine_tune():
    """Return path and content info for fine-tuning dataset (physician team)."""
    if not FINE_TUNE_FILE.exists():
        return {"path": str(FINE_TUNE_FILE), "count": 0, "message": "No cases yet."}
    count = sum(1 for _ in open(FINE_TUNE_FILE))
    return {"path": str(FINE_TUNE_FILE), "count": count, "format": "JSONL (OpenAI fine-tuning style)"}


@app.get("/export/urgent-care")
def export_urgent_care():
    """Return path and count for urgent care fine-tuning dataset."""
    if not URGENT_CARE_FILE.exists():
        return {"path": str(URGENT_CARE_FILE), "count": 0, "message": "No urgent care cases yet."}
    count = sum(1 for _ in open(URGENT_CARE_FILE))
    return {"path": str(URGENT_CARE_FILE), "count": count, "format": "JSONL (urgent care / PA fine-tuning)"}


@app.get("/")
def root():
    """Root route so GET / doesn't 404 (e.g. Render health check)."""
    return {
        "service": "Splint Advisor API",
        "docs": "/docs",
        "health": "/health",
        "diagnose": "POST /diagnose",
        "moltbook": "GET /moltbook-auth-url (auth URL for bots); optional X-Moltbook-Identity on POST /diagnose",
    }


@app.get("/health")
def health():
    return {"status": "ok", "openai_configured": bool(os.getenv("OPENAI_API_KEY"))}
