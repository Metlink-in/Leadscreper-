from __future__ import annotations

import logging
from datetime import datetime
from uuid import uuid4
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, Depends

from app.config import settings
from app.models.search import SearchRequest
from app.services.scraper_service import scrape_all
from app.services.db_service import db_service
from app.services.exceptions import APIError

from app.services.dependencies import require_user

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/api/search")
async def search(request: SearchRequest, http_request: Request, user = Depends(require_user)) -> dict:
    logger.info(
        "[REQUEST] POST /api/search | user=%s | industries=%s | categories=%s",
        user["email"], request.industries, request.categories,
    )
    
    api_keys = {
        "search_api_key": user.get("search_api_key"),
        "gemini_api_key": user.get("gemini_api_key"),
        "openai_api_key": user.get("openai_api_key"),
    }
    
    if not api_keys["search_api_key"]:
        raise HTTPException(status_code=400, detail="SearchAPI Key is missing. Please add it in your Settings.")

    try:
        max_results = min(request.max_results or settings.max_results_per_source, settings.max_results_per_source)
        leads = await scrape_all(
            categories=request.categories,
            industries=request.industries,
            country=request.country,
            city=request.city,
            keywords=request.keywords,
            platforms=request.platforms,
            max_results=max_results,
            enable_ai=request.enable_ai,
            user_id=str(user["_id"]),
            api_keys=api_keys
        )
    except APIError as e:
        logger.error(f"Search API failure: {e.message}")
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as exc:
        logger.error("[REQUEST] /api/search failed with error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))

    scored_leads = [lead for lead in leads if lead.ai_score is not None]
    unscored_leads = [lead for lead in leads if lead.ai_score is None]
    scored_leads.sort(key=lambda x: x.ai_score or 0, reverse=True)
    sorted_leads = scored_leads + unscored_leads

    search_id = uuid4().hex
    search_data = {
        "created_at": datetime.utcnow().isoformat(),
        "leads": sorted_leads,
        "meta": {
            "categories": request.categories,
            "industries": request.industries,
            "country": request.country,
            "city": request.city,
            "keywords": request.keywords,
            "platforms": request.platforms,
            "max_results": max_results,
            "enable_ai": request.enable_ai,
        },
    }

    db_search_data = {
        "created_at": search_data["created_at"],
        "meta": search_data["meta"],
        "leads": [lead.model_dump() for lead in sorted_leads],
        "summary": {
            "high_priority_leads": len([l for l in scored_leads if (l.ai_score or 0) >= 70]),
            "leads_with_contacts": len([l for l in sorted_leads if l.email or l.phone]),
            "total_leads": len(sorted_leads)
        }
    }
    await db_service.save_search(search_id, db_search_data, user_id=str(user["_id"]))

    leads_data = []
    for lead in sorted_leads[:max_results]:
        lead_dict = lead.model_dump()
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

@router.get("/api/history")
async def get_history(limit: int = 50, user = Depends(require_user)) -> dict:
    try:
        history = await db_service.get_search_history(user_id=str(user["_id"]), limit=limit)
        return {"history": history}
    except Exception as exc:
        logger.error("[REQUEST] /api/history failed: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to fetch history")

@router.get("/api/history/{search_id}")
async def get_history_detail(search_id: str, user = Depends(require_user)) -> dict:
    try:
        data = await db_service.get_search(search_id, user_id=str(user["_id"]))
        if not data:
            raise HTTPException(status_code=404, detail="Search not found")
            
        return {
            "search_id": search_id,
            "created_at": data["created_at"],
            "meta": data["meta"],
            "total": len(data["leads"]),
            "leads": data["leads"]
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("[REQUEST] /api/history/%s failed: %s", search_id, exc)
        raise HTTPException(status_code=500, detail="Failed to fetch history detail")

@router.delete("/api/history/{search_id}")
async def delete_search_history(search_id: str, user = Depends(require_user)):
    try:
        success = await db_service.delete_search(search_id, user_id=str(user["_id"]))
        if not success:
            raise HTTPException(status_code=404, detail="Search not found")
        return {"status": "success", "message": "Search deleted"}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("[REQUEST] DELETE /api/history/%s failed: %s", search_id, exc)
        raise HTTPException(status_code=500, detail="Failed to delete search")

@router.delete("/api/history")
async def clear_all_history(user = Depends(require_user)):
    try:
        count = await db_service.clear_all_searches(user_id=str(user["_id"]))
        return {"status": "success", "message": f"Cleared {count} searches"}
    except Exception as exc:
        logger.error("[REQUEST] DELETE /api/history failed: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to clear history")
