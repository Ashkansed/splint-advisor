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

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from nih import nih_suggest_splints_and_diagnosis, search_pubmed

load_dotenv()

# Optional: use OpenAI for AI diagnosis
try:
    from openai import OpenAI
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY")) if os.getenv("OPENAI_API_KEY") else None
except Exception:
    client = None

app = FastAPI(title="Splint Advisor API", version="2.0.0")

# CORS: when deployed, set CORS_ORIGINS to your frontend URL(s), e.g. https://your-app.vercel.app
_cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").strip().split(",")
_cors_origins = [o.strip() for o in _cors_origins if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)
CASES_FILE = DATA_DIR / "cases.jsonl"
FINE_TUNE_FILE = DATA_DIR / "fine_tune_dataset.jsonl"
URGENT_CARE_FILE = DATA_DIR / "urgent_care_cases.jsonl"  # For urgent care / PA fine-tuning


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


def save_case(case_id: str, input_data: dict, response: dict, source: str = "api"):
    """Append case to JSONL for review and fine-tuning."""
    record = {
        "case_id": case_id,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "source": source,
        "input": input_data,
        "output": response,
    }
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


def save_urgent_care_case(case_id: str, input_data: dict, response: dict):
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
    with open(URGENT_CARE_FILE, "a") as f:
        f.write(json.dumps(record) + "\n")


@app.post("/diagnose", response_model=DiagnosisResponse)
def diagnose(problem_input: ProblemInput):
    """Submit a potential problem; returns diagnosis, splint, PA/urgent care suggestions, and NIH-based suggestions. Logs JSON for physicians and urgent care."""
    case_id = str(uuid.uuid4())
    problem = (problem_input.problem or "").strip()
    if not problem:
        raise HTTPException(status_code=400, detail="Please provide a problem description.")

    result = ai_diagnosis_pa_urgent_care(problem, problem_input.optional_context)
    if result is None:
        result = rule_based_diagnosis(problem)
        result.setdefault("suggested_diagnosis", result.get("diagnosis_summary", ""))
        result.setdefault("other_recommendations", [])

    rec = result["recommended_splint"]
    if isinstance(rec, dict):
        rec_obj = SplintRecommendation(
            splint_name=rec.get("splint_name", "Unknown"),
            rationale=rec.get("rationale", ""),
            alternatives=rec.get("alternatives"),
            precautions=rec.get("precautions"),
        )
    else:
        rec_obj = SplintRecommendation(splint_name=str(rec), rationale=result.get("rationale", ""))

    # NIH/PubMed search for additional splints and diagnosis terms
    nih_data = nih_suggest_splints_and_diagnosis(problem, rec_obj.splint_name)
    result["nih_articles"] = nih_data["nih_articles"]
    result["additional_splints_from_nih"] = nih_data["additional_splints_from_nih"]
    result["suggested_diagnosis_terms_from_nih"] = nih_data["suggested_diagnosis_terms"]

    response_dict = {
        "case_id": case_id,
        "diagnosis_summary": result.get("diagnosis_summary", ""),
        "recommended_splint": rec_obj.model_dump(),
        "confidence": result.get("confidence", "medium"),
        "disclaimer": "This is an advisory tool only. Always confirm with a qualified clinician.",
        "suggested_diagnosis": result.get("suggested_diagnosis"),
        "other_recommendations": result.get("other_recommendations") or [],
        "nih_articles": result.get("nih_articles"),
        "additional_splints_from_nih": result.get("additional_splints_from_nih"),
        "suggested_diagnosis_terms_from_nih": result.get("suggested_diagnosis_terms_from_nih"),
    }

    save_case(case_id, {"problem": problem, "optional_context": problem_input.optional_context}, response_dict)
    save_urgent_care_case(case_id, {"problem": problem, "optional_context": problem_input.optional_context}, response_dict)

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


@app.get("/health")
def health():
    return {"status": "ok", "openai_configured": bool(os.getenv("OPENAI_API_KEY"))}
