"""
NIH/PubMed (NCBI E-utilities) search for orthopaedic/splint literature.
Used to suggest additional splints and problem (diagnosis) from evidence.
"""
import json
import re
import urllib.parse
import urllib.request

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


def search_pubmed(query: str, retmax: int = 5) -> list[dict]:
    """
    Search PubMed; return list of {pmid, title, snippet} for up to retmax results.
    """
    try:
        term = urllib.parse.quote(query)
        url = f"{EUTILS}/esearch.fcgi?db=pubmed&term={term}&retmax={retmax}&retmode=json&tool=splint_advisor&email=user@example.com"
        req = urllib.request.Request(url, headers={"User-Agent": "SplintAdvisor/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
    except Exception:
        return []

    id_list = data.get("esearchresult", {}).get("idlist", [])
    if not id_list:
        return []

    # Fetch summaries for PMIDs
    ids = ",".join(id_list)
    sum_url = f"{EUTILS}/esummary.fcgi?db=pubmed&id={ids}&retmode=json"
    try:
        req2 = urllib.request.Request(sum_url, headers={"User-Agent": "SplintAdvisor/1.0"})
        with urllib.request.urlopen(req2, timeout=10) as resp2:
            sum_data = json.loads(resp2.read().decode())
    except Exception:
        return []

    result = sum_data.get("result", {})
    out = []
    for pmid in id_list:
        doc = result.get(pmid, {})
        title = doc.get("title", "")
        out.append({"pmid": pmid, "title": title, "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"})
    return out


def nih_suggest_splints_and_diagnosis(problem: str, primary_splint: str) -> dict:
    """
    Query PubMed for upper extremity splint / orthopaedic literature related to the problem.
    Returns: nih_articles (list), additional_splints_suggested (list), suggested_diagnosis_terms (list).
    """
    # Build search: problem + orthopaedic splint
    safe = re.sub(r"[^\w\s-]", "", problem)[:80]
    query = f"({safe}) AND (upper extremity OR hand OR wrist OR orthopaedic) AND (splint OR immobilization)"
    articles = search_pubmed(query, retmax=5)

    additional_splints = []
    diagnosis_terms = set()

    # Extract splint types and diagnosis-related terms from titles (simple heuristic)
    splint_terms = [
        "volar", "thumb spica", "sugar-tong", "muenster", "mallet", "resting hand",
        "wrist splint", "finger splint", "elbow", "long arm", "cock-up", "dorsal",
        "extension", "thumb", "CMC", "PIP", "DIP", "orthosis"
    ]
    for art in articles:
        t = (art.get("title") or "").lower()
        for s in splint_terms:
            if s in t and s not in [x.lower() for x in additional_splints]:
                additional_splints.append(s.title())
        # Simple diagnosis-like phrases from title
        for word in ["fracture", "sprain", "tendon", "ligament", "carpal", "arthritis", "tunnel", "tendinitis", "tenosynovitis"]:
            if word in t:
                diagnosis_terms.add(word)

    # Dedupe and limit
    additional_splints = list(dict.fromkeys([s for s in additional_splints if s.lower() != primary_splint.lower()]))[:5]
    suggested_diagnosis_terms = list(diagnosis_terms)[:6]

    return {
        "nih_articles": articles,
        "additional_splints_from_nih": additional_splints,
        "suggested_diagnosis_terms": suggested_diagnosis_terms,
    }
