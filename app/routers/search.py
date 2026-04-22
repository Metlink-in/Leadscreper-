from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request

from app.config import settings
from app.models.search import SearchRequest
from app.services.scraper_service import scrape_all

router = APIRouter()


@router.post("/api/search")
async def search(request: SearchRequest, http_request: Request) -> dict:
    try:
        max_results = min(request.max_results or settings.max_results_per_source, settings.max_results_per_source)
        leads = await scrape_all(
            categories=request.categories,
            industries=request.industries,
            country=request.country,
            city=request.city,
            keywords=request.keywords,
            max_results=max_results,
            enable_ai=request.enable_ai,
        )

        # Sort leads by AI score (highest first) and filter out low-quality leads
        scored_leads = [lead for lead in leads if lead.ai_score is not None]
        unscored_leads = [lead for lead in leads if lead.ai_score is None]

        # Sort scored leads by score descending
        scored_leads.sort(key=lambda x: x.ai_score or 0, reverse=True)

        # Combine scored and unscored leads
        sorted_leads = scored_leads + unscored_leads

        search_id = uuid4().hex
        http_request.app.state.search_store[search_id] = {
            "created_at": datetime.utcnow().isoformat(),
            "leads": sorted_leads,
            "meta": {
                "categories": request.categories,
                "industries": request.industries,
                "country": request.country,
                "city": request.city,
                "keywords": request.keywords,
                "max_results": max_results,
                "enable_ai": request.enable_ai,
            },
        }

        # Prepare enhanced response with better presentation
        leads_data = []
        for lead in sorted_leads[:max_results]:
            lead_dict = lead.model_dump()
            # Add presentation enhancements
            lead_dict["contact_info_available"] = bool(lead.email or lead.phone)
            lead_dict["has_website"] = bool(lead.website)
            lead_dict["priority_score"] = lead.ai_score or 0
            leads_data.append(lead_dict)

        return {
            "search_id": search_id,
            "total": len(sorted_leads),
            "leads": leads_data,
            "summary": {
                "high_priority_leads": len([l for l in scored_leads if (l.ai_score or 0) >= 70]),
                "medium_priority_leads": len([l for l in scored_leads if 40 <= (l.ai_score or 0) < 70]),
                "low_priority_leads": len([l for l in scored_leads if (l.ai_score or 0) < 40]),
                "leads_with_contacts": len([l for l in sorted_leads if l.email or l.phone]),
                "leads_with_websites": len([l for l in sorted_leads if l.website]),
            }
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
