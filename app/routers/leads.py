from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, Request

router = APIRouter()


def _filter_lead(lead: dict, industry: Optional[str], category: Optional[int], country: Optional[str], min_score: Optional[int], keywords: Optional[str]) -> bool:
    if industry and lead.get("industry", "").lower() != industry.lower():
        return False
    if category and lead.get("category") != category:
        return False
    if country and country.lower() not in lead.get("location", "").lower():
        return False
    if min_score is not None:
        score = lead.get("ai_score")
        if score is None or score < min_score:
            return False
    if keywords:
        terms = [term.strip().lower() for term in keywords.split(",") if term.strip()]
        text = " ".join([lead.get("name", ""), lead.get("description", ""), " ".join(lead.get("keywords_matched", []))]).lower()
        if not any(term in text for term in terms):
            return False
    return True


@router.get("/api/leads")
async def get_leads(
    request: Request,
    search_id: str,
    industry: Optional[str] = Query(None),
    category: Optional[int] = Query(None),
    country: Optional[str] = Query(None),
    min_score: Optional[int] = Query(None, ge=0, le=100),
    keywords: Optional[str] = Query(None),
) -> dict:
    store = request.app.state.search_store
    if search_id not in store:
        raise HTTPException(status_code=404, detail="Search ID not found")
    raw_leads = [lead.model_dump() for lead in store[search_id]["leads"]]
    filtered = [lead for lead in raw_leads if _filter_lead(lead, industry, category, country, min_score, keywords)]
    return {
        "search_id": search_id,
        "total": len(filtered),
        "leads": filtered,
    }
