"""
Fuzzy aggregation of solutions between two agents:
- Agent 1: PA/urgent care (clinical) diagnosis and splint recommendation
- Agent 2: NIH/PubMed (evidence) suggestions: additional splints, diagnosis terms

Uses simple fuzzy sets (membership, weighted fusion, defuzzification) to combine
outputs without adding external fuzzy libraries.
"""
from __future__ import annotations

from typing import Any


# --- Confidence: linguistic ↔ numeric ---
CONFIDENCE_TO_NUMERIC = {"high": 0.85, "medium": 0.5, "low": 0.2}
NUMERIC_TO_CONFIDENCE = [(0.7, "high"), (0.35, "medium"), (0.0, "low")]


def confidence_to_numeric(c: str) -> float:
    return CONFIDENCE_TO_NUMERIC.get((c or "medium").lower(), 0.5)


def defuzzify_confidence(x: float) -> str:
    """Map fused numeric confidence back to high/medium/low."""
    for threshold, label in NUMERIC_TO_CONFIDENCE:
        if x >= threshold:
            return label
    return "low"


def membership_triangular(x: float, a: float, b: float, c: float) -> float:
    """Triangular membership: peak at b, zero outside [a, c]."""
    if x <= a or x >= c:
        return 0.0
    if x <= b:
        return (x - a) / (b - a) if a != b else 1.0
    return (c - x) / (c - b) if b != c else 1.0


def nih_evidence_strength(n_articles: int, n_terms: int, n_splints: int) -> float:
    """
    Fuzzy strength of NIH evidence: more articles and extracted terms/splints
    increase membership in "strong evidence".
    """
    article_mu = membership_triangular(n_articles, 0, 3, 6)  # peak at 3+ articles
    term_mu = min(1.0, (n_terms + n_splints) / 6)  # simple ramp
    return 0.6 * article_mu + 0.4 * term_mu


def fuse_confidence(
    clinical_confidence: str,
    nih_articles_count: int,
    nih_terms_count: int,
    nih_splints_count: int,
    w_clinical: float = 0.7,
) -> str:
    """
    Fuse clinical confidence with NIH evidence strength.
    w_clinical: weight for agent1 (PA); (1 - w_clinical) for NIH.
    """
    c_num = confidence_to_numeric(clinical_confidence)
    nih_str = nih_evidence_strength(nih_articles_count, nih_terms_count, nih_splints_count)
    fused = w_clinical * c_num + (1 - w_clinical) * nih_str
    fused = max(0.0, min(1.0, fused))
    return defuzzify_confidence(fused)


def splint_membership_from_nih(splint_name: str, nih_articles: list[dict]) -> float:
    """
    Membership of a splint in "supported by literature": how many article titles
    mention this splint type (normalized to [0,1]).
    """
    if not nih_articles:
        return 0.0
    key = splint_name.lower()
    count = sum(1 for a in nih_articles if key in (a.get("title") or "").lower())
    return membership_triangular(count, 0, 1, 4)  # 1+ mention gives some support


def fuse_splints(
    primary_splint: dict[str, Any],
    additional_splints_from_nih: list[str],
    nih_articles: list[dict],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """
    Aggregate primary splint (agent1) with NIH suggestions.
    Returns:
      - fused_primary: same as primary_splint with optional fuzzy_confidence
      - fused_alternatives: list of {splint_name, source, membership} for UI/ranking
    """
    fused_primary = dict(primary_splint)
    alternatives = list(primary_splint.get("alternatives") or [])

    # Build alternatives with membership: primary's list first, then NIH with scores
    seen = {primary_splint.get("splint_name", "").lower()}
    fused_alt_list: list[dict[str, Any]] = []

    for alt in alternatives:
        if isinstance(alt, dict):
            name = alt.get("splint_name") or alt.get("name") or str(alt)
        else:
            name = str(alt)
        if name.lower() not in seen:
            seen.add(name.lower())
            fused_alt_list.append({
                "splint_name": name,
                "source": "clinical",
                "membership": 1.0,
            })

    for s in additional_splints_from_nih or []:
        if s.lower() in seen:
            continue
        seen.add(s.lower())
        mu = splint_membership_from_nih(s, nih_articles or [])
        fused_alt_list.append({
            "splint_name": s,
            "source": "nih",
            "membership": round(mu, 2),
        })

    # Sort by membership descending so stronger evidence first
    fused_alt_list.sort(key=lambda x: (-x["membership"], x["splint_name"]))

    fused_primary["alternatives_with_scores"] = fused_alt_list
    return fused_primary, fused_alt_list


def fuse_diagnosis_terms(
    suggested_diagnosis: str | None,
    suggested_diagnosis_terms_from_nih: list[str] | None,
    w_clinical: float = 0.6,
) -> tuple[str | None, list[dict[str, Any]]]:
    """
    Fuse clinical suggested_diagnosis (agent1) with NIH diagnosis terms (agent2).
    Returns:
      - fused_suggested_diagnosis: clinical string (unchanged for display)
      - aggregated_terms: list of {term, source, weight} for combined view
    """
    terms_out: list[dict[str, Any]] = []

    if suggested_diagnosis and suggested_diagnosis.strip():
        terms_out.append({
            "term": suggested_diagnosis.strip(),
            "source": "clinical",
            "weight": round(w_clinical, 2),
        })

    for t in (suggested_diagnosis_terms_from_nih or []):
        if not t or not str(t).strip():
            continue
        term = str(t).strip()
        terms_out.append({
            "term": term,
            "source": "nih",
            "weight": round(1.0 - w_clinical, 2),
        })

    return suggested_diagnosis, terms_out


def fuse_recommendations(
    other_recommendations: list[str] | None,
    nih_articles: list[dict] | None,
    nih_priority_bonus: float = 0.3,
) -> list[dict[str, Any]]:
    """
    Merge clinical other_recommendations with optional NIH-derived actions.
    Returns list of {recommendation, source, priority} (priority in [0,1]).
    """
    out: list[dict[str, Any]] = []
    for r in (other_recommendations or []):
        if r and str(r).strip():
            out.append({
                "recommendation": str(r).strip(),
                "source": "clinical",
                "priority": 1.0,
            })

    if nih_articles:
        out.append({
            "recommendation": "Consider literature review (PubMed results attached).",
            "source": "nih",
            "priority": round(nih_priority_bonus, 2),
        })

    out.sort(key=lambda x: (-x["priority"], x["recommendation"]))
    return out


def aggregate_two_agents(
    agent1_result: dict[str, Any],
    agent2_result: dict[str, Any],
    w_clinical: float = 0.7,
) -> dict[str, Any]:
    """
    Fuzzy aggregation of agent1 (PA/urgent care) and agent2 (NIH) outputs.

    - agent1_result: diagnosis_summary, suggested_diagnosis, recommended_splint,
      other_recommendations, confidence (and any extra keys preserved).
    - agent2_result: nih_articles, additional_splints_from_nih,
      suggested_diagnosis_terms (or suggested_diagnosis_terms_from_nih).

    Returns a single fused result with:
      - All agent1 fields preserved; confidence and splint/alternatives fused.
      - Fuzzy fields: fused_confidence, alternatives_with_scores,
        aggregated_diagnosis_terms, fused_recommendations (optional).
    """
    # Aliases for NIH keys
    nih_articles = agent2_result.get("nih_articles") or []
    additional_splints = agent2_result.get("additional_splints_from_nih") or agent2_result.get("additional_splints") or []
    nih_terms = agent2_result.get("suggested_diagnosis_terms_from_nih") or agent2_result.get("suggested_diagnosis_terms") or []

    fused: dict[str, Any] = dict(agent1_result)

    # 1) Fuse confidence
    fused["confidence"] = fuse_confidence(
        agent1_result.get("confidence") or "medium",
        len(nih_articles),
        len(nih_terms),
        len(additional_splints),
        w_clinical=w_clinical,
    )
    fused["fused_confidence_numeric"] = round(
        confidence_to_numeric(fused["confidence"]) * 100,
    )  # 0–100 for UI

    # 2) Fuse splints
    rec = agent1_result.get("recommended_splint") or {}
    if isinstance(rec, dict):
        primary = rec
    else:
        primary = {"splint_name": str(rec), "rationale": "", "alternatives": []}
    fused_primary, alt_list = fuse_splints(primary, additional_splints, nih_articles)
    fused["recommended_splint"] = fused_primary
    fused["alternatives_with_scores"] = alt_list

    # 3) Fuse diagnosis terms (keep suggested_diagnosis, add aggregated list)
    suggested = agent1_result.get("suggested_diagnosis")
    _, agg_terms = fuse_diagnosis_terms(suggested, nih_terms, w_clinical=0.6)
    fused["aggregated_diagnosis_terms"] = agg_terms

    # 4) Fuse recommendations
    other = agent1_result.get("other_recommendations") or []
    fused["fused_recommendations"] = fuse_recommendations(other, nih_articles)

    # Keep NIH raw data for API consumers
    fused["nih_articles"] = agent2_result.get("nih_articles")
    fused["additional_splints_from_nih"] = additional_splints
    fused["suggested_diagnosis_terms_from_nih"] = nih_terms

    return fused
